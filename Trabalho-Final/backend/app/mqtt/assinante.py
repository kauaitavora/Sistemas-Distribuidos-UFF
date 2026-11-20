"""
Assinante MQTT do backend: processo separado da API.

Conecta ao broker por TCP (porta 1883), assina as posições dos ônibus e,
por enquanto, apenas mostra cada mensagem recebida. A validação e a gravação
no banco entram nos próximos passos.
"""

import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.enums import CallbackAPIVersion

# Carrega o .env da pasta backend (duas pastas acima: mqtt -> app -> backend).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Endereço do broker. O backend usa TCP; só o navegador precisa de WebSocket.
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Filtro de assinatura. O "+" casa exatamente um nível,
# então só chegam tópicos no formato rotas/<rota_id>/<veiculo_id>.
TOPICO_POSICOES = "rotas/+/+"

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
    cliente.subscribe(TOPICO_POSICOES, qos=QOS)
    print(f"Assinado: {TOPICO_POSICOES} (QoS {QOS})")


def ao_receber(cliente, userdata, mensagem):
    """Chamada pelo paho a cada mensagem recebida em um tópico assinado."""
    conteudo = mensagem.payload.decode("utf-8", errors="replace")
    print(f"[{mensagem.topic}] {conteudo}")


def main() -> None:
    # O paho-mqtt 2.x exige escolher a versão da API de callbacks. Usamos a VERSION2.
    # O MQTT.pdf e o cliente-LWT.py usam a API antiga (1.x), em que o on_connect
    # recebe (client, userdata, flags, rc); na VERSION2 ele recebe também
    # reason_code e properties.
    cliente = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        clean_session=False,  # sessão persistente: o broker lembra da assinatura e guarda mensagens
    )
    cliente.on_connect = ao_conectar
    cliente.on_message = ao_receber

    try:
        # keepalive=60, como no MQTT.pdf: sem tráfego por 60 s, o cliente manda um "ping".
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