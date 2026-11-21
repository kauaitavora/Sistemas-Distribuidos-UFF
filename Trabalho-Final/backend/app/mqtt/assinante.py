# Trabalho-Final/backend/app/mqtt/assinante.py
"""
Assinante MQTT do backend: processo separado da API.

Conecta ao broker por TCP (porta 1883) e assina dois tipos de tópico:
- rotas/<rota_id>/<veiculo_id>: posições, validadas e gravadas no PostgreSQL;
- status/<veiculo_id>: online/offline, inclusive o testamento (LWT) publicado pelo broker.

Modo réplica (eleição de líder pelo algoritmo do valentão; só a líder grava).
"""

import argparse
import os
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.enums import CallbackAPIVersion

from app.mqtt.eleicao import Eleicao
from app.mqtt.gravacao import gravar_posicao, gravar_status
from app.mqtt.validacao import MensagemInvalida, validar_posicao, validar_status

# Carrega o .env da pasta backend (duas pastas acima: mqtt -> app -> backend).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Endereço do broker. O backend usa TCP; só o navegador precisa de WebSocket.
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Filtro de assinatura. O "+" casa exatamente um nível,
# então só chegam tópicos no formato rotas/<rota_id>/<veiculo_id>.
TOPICO_POSICOES = "rotas/+/+"

# Estado de cada ônibus: online/offline, inclusive o LWT.
TOPICO_STATUS = "status/+"

# QoS 1 = "pelo menos uma vez": não perde mensagens, mas pode repeti-las.
# As repetições são barradas pela restrição única do banco.
QOS = 1

# Identificador fixo do assinante no broker. Junto com clean_session=False,
# faz o broker guardar as mensagens QoS 1 enquanto o assinante estiver desligado
# e entregá-las quando ele voltar (desacoplamento no tempo).
CLIENT_ID = "busuff-assinante"

# Keepalive das réplicas: menor que o do modo único (60 s) para que a queda da
# líder seja percebida rápido (cerca de 1,5 x 5 s = 7,5 s sem sinal de rede).
KEEPALIVE_REPLICA = 5

# Eleição desta réplica (None no modo único, em que o assinante sempre grava).
eleicao = None


def ao_conectar(cliente, userdata, flags, reason_code, properties):
    """Chamada pelo paho quando a tentativa de conexão termina (com sucesso ou não)."""
    if reason_code.is_failure:
        print(f"Falha ao conectar no broker: {reason_code}")
        return
    print(f"Conectado ao broker {MQTT_HOST}:{MQTT_PORT}")
    # Assinar AQUI, e não fora do on_connect:
    # se a conexão cair e voltar, esta função roda de novo e a assinatura é refeita.
    topicos = [(TOPICO_POSICOES, QOS), (TOPICO_STATUS, QOS)]
    if eleicao is not None:
        topicos += eleicao.topicos()  # caixa de entrada, anúncio do líder e saídas
    cliente.subscribe(topicos)
    print(f"Assinado: {', '.join(topico for topico, _ in topicos)} (QoS {QOS})")
    if eleicao is not None:
        # Valentão: um processo que inicia (ou se recupera) começa uma eleição.
        eleicao.iniciar_eleicao("réplica conectada")


def ao_receber(cliente, userdata, mensagem):
    """Chamada pelo paho a cada mensagem recebida: separa eleição, seguidora e líder."""
    if eleicao is not None:
        if mensagem.topic.startswith("eleicao/"):
            eleicao.tratar(mensagem)
            return
        if not eleicao.deve_processar(mensagem):
            return  # seguidora: a mensagem foi guardada no buffer, sem gravar
    processar_mensagem(mensagem)


def processar_mensagem(mensagem):
    """Valida e grava uma posição ou um status (feito só pela líder, no modo réplica)."""
    try:
        if mensagem.topic.startswith("status/"):
            tratar_status(mensagem)
        else:
            tratar_posicao(mensagem)
    except MensagemInvalida as erro:
        # Mensagem fora do contrato: descartada e registrada, e o assinante segue.
        print(f"[DESCARTADA] {mensagem.topic}: {erro}")
    except Exception as erro:
        # Rede de segurança: no paho, um erro não tratado aqui dentro derruba o
        # loop e o assinante para. Uma mensagem ruim não pode derrubar o serviço.
        print(f"[ERRO INESPERADO] {mensagem.topic}: {erro!r}")


def tratar_posicao(mensagem):
    """Valida e grava uma posição (rotas/<rota_id>/<veiculo_id>)."""
    posicao = validar_posicao(mensagem.topic, mensagem.payload)
    if gravar_posicao(posicao):
        print(
            f"[GRAVADA] {posicao.veiculo_id} na {posicao.rota_id}: "
            f"({posicao.lat}, {posicao.lng}) às {posicao.timestamp:%H:%M:%S} UTC"
        )
    else:
        # Cópia repetida (QoS 1): o banco já tinha esta posição e a ignorou.
        print(f"[DUPLICADA] {posicao.veiculo_id} às {posicao.timestamp:%H:%M:%S} UTC: ignorada")


def tratar_status(mensagem):
    """Atualiza o estado online/offline de um ônibus (status/<veiculo_id>, inclusive o LWT)."""
    veiculo_id, online = validar_status(mensagem.topic, mensagem.payload)
    estado = "online" if online else "offline"
    # retain=True: é o último estado guardado pelo broker, entregue logo ao assinar
    # (não é um evento novo).
    origem = " (mensagem retida)" if mensagem.retain else ""
    if gravar_status(veiculo_id, online):
        print(f"[STATUS] {veiculo_id} agora está {estado}{origem}")
    else:
        print(f"[STATUS] {veiculo_id} continua {estado}{origem}: nada mudou")


def main() -> None:
    global eleicao

    # Argumentos opcionais: sem --replica, o assinante funciona como antes (sempre grava).
    parser = argparse.ArgumentParser(description="Assinante MQTT do backend Cadê o BusUFF?")
    parser.add_argument("--replica", type=int, help="número desta réplica (de 1 a --total)")
    parser.add_argument("--total", type=int, default=3, help="quantidade de réplicas (padrão: 3)")
    args = parser.parse_args()
    if args.replica is not None and not 1 <= args.replica <= args.total:
        parser.error(f"--replica deve estar entre 1 e {args.total}")

    modo_replica = args.replica is not None
    # Cada réplica precisa de um client_id próprio: o broker derruba a conexão
    # antiga quando outro cliente conecta com o mesmo id.
    client_id = f"{CLIENT_ID}-{args.replica}" if modo_replica else CLIENT_ID

    # O paho-mqtt 2.x exige escolher a versão da API de callbacks. Optou-se pelo VERSION2:
    # ele recebe reason_code e properties.
    cliente = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=client_id,
        clean_session=False,  # sessão persistente: o broker lembra da assinatura e guarda mensagens
    )
    cliente.on_connect = ao_conectar
    cliente.on_message = ao_receber

    if modo_replica:
        eleicao = Eleicao(cliente, args.replica, args.total, processar_mensagem)
        # Testamento registrado ANTES de conectar.
        eleicao.registrar_testamento()
        print(f"Modo réplica: réplica {args.replica} de {args.total}")

    try:
        cliente.connect(MQTT_HOST, MQTT_PORT, keepalive=KEEPALIVE_REPLICA if modo_replica else 60)
    except ConnectionRefusedError:
        print(f"Não foi possível conectar em {MQTT_HOST}:{MQTT_PORT}. O HiveMQ está rodando?")
        return

    # loop_start roda a rede numa thread separada e reconecta sozinho se a conexão cair;
    # o programa principal só espera o Ctrl+C.
    cliente.loop_start()
    print("Aguardando mensagens... (Ctrl+C para sair)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrando o assinante.")
        if eleicao is not None:
            # Saída normal não dispara o LWT: avisa as outras réplicas explicitamente
            # e espera a confirmação do broker (PUBACK) por até 2 s.
            try:
                eleicao.avisar_saida().wait_for_publish(timeout=2)
            except (RuntimeError, ValueError) as erro:
                print(f"Não foi possível avisar a saída: {erro}")
        cliente.disconnect()
        cliente.loop_stop()


if __name__ == "__main__":
    main()
