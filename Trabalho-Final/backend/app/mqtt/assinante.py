"""
Assinante MQTT do backend: processo separado da API.

Conecta ao broker por TCP (porta 1883) e assina dois tipos de tópico:
- rotas/<rota_id>/<veiculo_id>: posições, validadas e gravadas no PostgreSQL;
- status/<veiculo_id>: online/offline, inclusive o testamento (LWT) publicado pelo broker.
"""

import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.enums import CallbackAPIVersion

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
# e entregá-las quando ele voltar.
CLIENT_ID = "busuff-assinante"


def ao_conectar(cliente, userdata, flags, reason_code, properties):
    """Chamada pelo paho quando a tentativa de conexão termina (com sucesso ou não)."""
    if reason_code.is_failure:
        print(f"Falha ao conectar no broker: {reason_code}")
        return
    print(f"Conectado ao broker {MQTT_HOST}:{MQTT_PORT}")
    # Assinar AQUI, e não fora do on_connect:
    # se a conexão cair e voltar, esta função roda de novo e a assinatura é refeita.
    cliente.subscribe([(TOPICO_POSICOES, QOS), (TOPICO_STATUS, QOS)])
    print(f"Assinado: {TOPICO_POSICOES} e {TOPICO_STATUS} (QoS {QOS})")


def ao_receber(cliente, userdata, mensagem):
    """Chamada pelo paho a cada mensagem recebida: separa status de posição."""
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
        # loop_forever e o assinante para. Uma mensagem ruim não pode derrubar o serviço.
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
    # O paho-mqtt 2.x exige escolher a versão da API de callbacks. Foi usada a VERSION2.
    cliente = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        clean_session=False,  # sessão persistente: o broker lembra da assinatura e guarda mensagens
    )
    cliente.on_connect = ao_conectar
    cliente.on_message = ao_receber

    try:
        # keepalive=60: sem tráfego por 60 s, o cliente manda um "ping".
        cliente.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    except ConnectionRefusedError:
        print(f"Não foi possível conectar em {MQTT_HOST}:{MQTT_PORT}. O HiveMQ está rodando?")
        return

    print("Aguardando mensagens... (Ctrl+C para sair)")
    try:
        # loop_forever cuida da rede e reconecta sozinho se a conexão cair.
        cliente.loop_forever()
    except KeyboardInterrupt:
        print("Encerrando o assinante.")
        cliente.disconnect()


if __name__ == "__main__":
    main()
