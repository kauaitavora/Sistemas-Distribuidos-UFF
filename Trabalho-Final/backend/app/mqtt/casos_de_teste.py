"""
Publica mensagens de teste, válidas e inválidas, para conferir a validação do assinante.
"""

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


def posicao(timestamp_ms: int, lat: float = -22.505253) -> dict:
    """Monta uma posição no formato do Capacitor."""
    return {
        "timestamp": timestamp_ms,
        "coords": {
            "latitude": lat,
            "longitude": -41.920643,
            "accuracy": 10.0,
            "speed": 11.0,
            "heading": 0.0,
        },
    }


def montar_casos() -> list[tuple[str, str, str, str]]:
    """Lista de casos: (descrição, tópico, conteúdo, o que o assinante deve mostrar)."""
    agora = int(time.time() * 1000)
    topico = "rotas/rota-1/onibus-01"
    return [
        # --- Validação ---
        ("válida", topico, json.dumps(posicao(agora)), "[GRAVADA]"),
        ("JSON quebrado", topico, '{"timestamp": 123, "coords": ', "[DESCARTADA]"),
        ("sem coords", topico, json.dumps({"timestamp": agora}), "[DESCARTADA]"),
        ("latitude fora da faixa", topico, json.dumps(posicao(agora, lat=200)), "[DESCARTADA]"),
        ("timestamp em segundos", topico, json.dumps(posicao(agora // 1000)), "[DESCARTADA]"),
        ("maiúscula no tópico", "rotas/Rota-1/onibus-01", json.dumps(posicao(agora)), "[DESCARTADA]"),
        (
            "horario_id com tipo errado",
            topico,
            json.dumps({**posicao(agora + 1000), "horario_id": "sete"}),
            "[GRAVADA] sem horário",
        ),
        (
            "tópico no formato antigo",
            "rotas/rota-1",
            json.dumps(posicao(agora)),
            "nada (o filtro rotas/+/+ não entrega)",
        ),
        # --- Regras do banco ---
        ("duplicada: 1ª cópia", topico, json.dumps(posicao(agora + 2000)), "[GRAVADA]"),
        ("duplicada: 2ª cópia (mesmo timestamp)", topico, json.dumps(posicao(agora + 2000)), "[DUPLICADA]"),
        (
            "ônibus desconhecido",
            "rotas/rota-1/onibus-99",
            json.dumps(posicao(agora)),
            "[GRAVADA] (onibus-99 cadastrado)",
        ),
        ("rota inexistente", "rotas/rota-9/onibus-01", json.dumps(posicao(agora + 3000)), "[DESCARTADA]"),
        (
            "horário de outra rota (id 4 é da rota-2)",
            topico,
            json.dumps({**posicao(agora + 4000), "horario_id": 4}),
            "[AVISO] e depois [GRAVADA]",
        ),
        (
            "horário válido (id 1 é da rota-1)",
            topico,
            json.dumps({**posicao(agora + 5000), "horario_id": 1}),
            "[GRAVADA] com horário",
        ),
    ]


def main() -> None:
    cliente = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    cliente.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    cliente.loop_start()  # thread de rede, necessária para receber o PUBACK do QoS 1

    for numero, (descricao, topico, conteudo, esperado) in enumerate(montar_casos(), start=1):
        cliente.publish(topico, conteudo, qos=1).wait_for_publish()
        print(f"{numero}. {descricao} -> esperado no assinante: {esperado}")
        time.sleep(0.5)  # pequena pausa para facilitar a leitura dos dois terminais

    cliente.disconnect()
    cliente.loop_stop()


if __name__ == "__main__":
    main()
