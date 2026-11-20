"""
Simulador do app do motorista, apenas para testar o backend.

Publica posições no MESMO formato que o app publica hoje (objeto Position do
Capacitor), no tópico rotas/<rota_id>/<veiculo_id>, uma por segundo. 
"""

import argparse
import json
import os
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.enums import CallbackAPIVersion

# Carrega o .env da pasta backend (duas pastas acima: mqtt -> app -> backend).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Ponto de partida do trajeto simulado (o mesmo do exemplo do CONTRATO.md).
LAT_INICIAL = -22.505253
LNG_INICIAL = -41.920643


def montar_posicao(passo: int) -> dict:
    """Monta uma posição no formato do Capacitor, andando um pouco para o norte a cada passo."""
    return {
        "timestamp": int(time.time() * 1000),  # milissegundos desde 1970 (UTC), como no Capacitor
        "coords": {
            "latitude": LAT_INICIAL + passo * 0.0001,  # cerca de 11 m por passo
            "longitude": LNG_INICIAL,
            "accuracy": 10.0,
            "altitude": None,
            "altitudeAccuracy": None,
            "speed": 11.0,   # em m/s (cerca de 40 km/h)
            "heading": 0.0,  # rumo norte
        },
    }


def main() -> None:
    # Argumentos opcionais da linha de comando (com valores padrão).
    parser = argparse.ArgumentParser(description="Simula o app do motorista publicando posições.")
    parser.add_argument("--rota", default="rota-1")
    parser.add_argument("--veiculo", default="onibus-01")
    parser.add_argument("--quantidade", type=int, default=5)
    args = parser.parse_args()

    topico = f"rotas/{args.rota}/{args.veiculo}"

    cliente = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    cliente.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    # loop_start roda a parte de rede numa thread separada; ela é necessária
    # para receber o PUBACK, que é a confirmação do QoS 1.
    cliente.loop_start()

    for passo in range(args.quantidade):
        payload = json.dumps(montar_posicao(passo))
        info = cliente.publish(topico, payload, qos=1)
        info.wait_for_publish()  # espera o broker confirmar (PUBACK) antes de seguir
        print(f"Publicado em {topico}: {payload}")
        time.sleep(1)  # mesmo intervalo do app (1 s)

    cliente.disconnect()
    cliente.loop_stop()


if __name__ == "__main__":
    main()
