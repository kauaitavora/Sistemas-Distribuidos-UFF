# Trabalho-Final/backend/app/mqtt/simulador.py
"""
Simulador do app do motorista, apenas para testar o backend.

Segue:
- posições no formato do Capacitor, em rotas/<rota_id>/<veiculo_id>, a cada 1 s;
- testamento (LWT) registrado ao conectar, "online" logo depois e
  "offline" ao encerrar normalmente.

Com --sem-sinal, simula um celular que perde a conexão sem avisar: o simulador
para de mandar os "pings" do keepalive, e o broker publica o LWT por ele.
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

# Keepalive: sem tráfego por 15 s, o cliente manda um "ping".
# Se o broker ficar cerca de 1,5 x 15 s sem ouvir nada, considera o cliente morto
# e publica o testamento (LWT).
KEEPALIVE = 15

# Ponto de partida do trajeto simulado.
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


def status(veiculo: str, estado: str) -> str:
    """Conteúdo de uma mensagem de status (CONTRATO.md, seção 4)."""
    return json.dumps({"veiculo_id": veiculo, "estado": estado})


def main() -> None:
    # Argumentos opcionais da linha de comando (com valores padrão).
    parser = argparse.ArgumentParser(description="Simula o app do motorista publicando posições.")
    parser.add_argument("--rota", default="rota-1")
    parser.add_argument("--veiculo", default="onibus-01")
    parser.add_argument("--quantidade", type=int, default=5)
    parser.add_argument(
        "--sem-sinal",
        action="store_true",
        help="ao final, simula perda de sinal (sem desconectar) para o broker disparar o LWT",
    )
    args = parser.parse_args()

    topico_posicao = f"rotas/{args.rota}/{args.veiculo}"
    topico_status = f"status/{args.veiculo}"

    cliente = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)

    # Testamento (LWT): registrado ANTES de conectar. O broker guarda esta mensagem
    # e só a publica se a conexão cair sem um DISCONNECT (falha do cliente).
    cliente.will_set(topico_status, status(args.veiculo, "offline"), qos=1, retain=True)

    cliente.connect(MQTT_HOST, MQTT_PORT, keepalive=KEEPALIVE)
    # loop_start roda a parte de rede numa thread separada (PUBACKs e "pings" do keepalive).
    cliente.loop_start()

    # Avisa que o ônibus entrou em serviço. retain=True: quem assinar depois recebe este estado.
    cliente.publish(topico_status, status(args.veiculo, "online"), qos=1, retain=True).wait_for_publish()
    print(f"Status publicado em {topico_status}: online")

    for passo in range(args.quantidade):
        payload = json.dumps(montar_posicao(passo))
        cliente.publish(topico_posicao, payload, qos=1).wait_for_publish()  # espera o PUBACK
        print(f"Publicado em {topico_posicao}: {payload}")
        time.sleep(1)  # mesmo intervalo do app (1 s)

    if args.sem_sinal:
        # Para a thread de rede SEM desconectar: a conexão continua aberta, mas
        # nenhum "ping" é enviado, como num celular que perdeu o sinal.
        # O broker só percebe pela falta de comunicação (tempo limite) e publica o LWT.
        cliente.loop_stop()
        espera = KEEPALIVE * 3
        print(f"Simulando perda de sinal por {espera} s; o LWT deve aparecer no assinante em ~22 s...")
        time.sleep(espera)
        print("Fim da simulação (o processo termina sem DISCONNECT).")
        return

    # Encerramento normal: avisa "offline" e só então desconecta.
    # Um DISCONNECT normal NÃO dispara o LWT, por isso o aviso precisa ser explícito.
    cliente.publish(topico_status, status(args.veiculo, "offline"), qos=1, retain=True).wait_for_publish()
    print(f"Status publicado em {topico_status}: offline")
    cliente.disconnect()
    cliente.loop_stop()


if __name__ == "__main__":
    main()
