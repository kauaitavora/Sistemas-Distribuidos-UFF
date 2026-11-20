"""
Validação das mensagens de posição.

Recebe o tópico e o conteúdo brutos e devolve uma posição "limpa"
(PosicaoRecebida) ou levanta MensagemInvalida explicando o motivo.

Aqui só entram as regras que não dependem do banco. 

Princípio fim a fim (Saltzer): o broker entrega qualquer coisa que for publicada;
só a ponta que usa os dados (o backend) pode garantir que eles fazem sentido.
"""

import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

# Formato dos ids: minúsculas sem acento, números e hífen, até 32 caracteres.
PADRAO_ID = re.compile(r"[a-z0-9-]{1,32}")

# Timestamps anteriores a 01/01/2020 (em milissegundos) são recusados.
# Isso pega, por exemplo, um app que mande segundos em vez de milissegundos.
TIMESTAMP_MINIMO_MS = 1_577_836_800_000

# Tolerância para o relógio do celular estar adiantado em relação ao servidor.
TOLERANCIA_FUTURO_MS = 10 * 60 * 1000  # 10 minutos


class MensagemInvalida(Exception):
    """Mensagem fora do contrato; o texto da exceção explica o motivo (vai para o log)."""


@dataclass
class PosicaoRecebida:
    """Posição já validada e convertida, pronta para ser gravada no banco."""

    rota_id: str
    veiculo_id: str
    timestamp: datetime  # em UTC
    lat: float
    lng: float
    precisao_m: float | None
    velocidade_ms: float | None
    direcao_graus: float | None
    horario_id: int | None


def _e_numero(valor) -> bool:
    """True se o valor for um número finito (bool conta como int em Python, então é excluído)."""
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
    )


def validar_topico(topico: str) -> tuple[str, str]:
    """Separa rotas/<rota_id>/<veiculo_id> e confere o formato dos dois ids."""
    partes = topico.split("/")
    if len(partes) != 3 or partes[0] != "rotas":
        raise MensagemInvalida(f"tópico fora do formato rotas/<rota_id>/<veiculo_id>: {topico}")
    _, rota_id, veiculo_id = partes
    if not PADRAO_ID.fullmatch(rota_id):
        raise MensagemInvalida(f"rota_id inválido no tópico: {rota_id!r}")
    if not PADRAO_ID.fullmatch(veiculo_id):
        raise MensagemInvalida(f"veiculo_id inválido no tópico: {veiculo_id!r}")
    return rota_id, veiculo_id


def _coordenada(coords: dict, campo: str, limite: float) -> float:
    """Lê latitude ou longitude (obrigatórias) e confere a faixa [-limite, limite]."""
    valor = coords.get(campo)
    if not _e_numero(valor):
        raise MensagemInvalida(f"coords.{campo} ausente ou não numérico: {valor!r}")
    if not -limite <= valor <= limite:
        raise MensagemInvalida(f"coords.{campo} fora da faixa [-{limite}, {limite}]: {valor}")
    return float(valor)


def _opcional(valor, minimo: float, maximo: float) -> float | None:
    """Campo opcional: se vier inválido ou fora da faixa, vira None em vez de recusar a mensagem."""
    if _e_numero(valor) and minimo <= valor <= maximo:
        return float(valor)
    return None


def _converter_timestamp(valor) -> datetime:
    """Converte o timestamp do Capacitor (milissegundos desde 1970, UTC) em data e hora UTC."""
    if not _e_numero(valor):
        raise MensagemInvalida(f"timestamp ausente ou não numérico: {valor!r}")
    agora_ms = time.time() * 1000
    if valor < TIMESTAMP_MINIMO_MS:
        raise MensagemInvalida(f"timestamp anterior a 2020 (está em segundos?): {valor}")
    if valor > agora_ms + TOLERANCIA_FUTURO_MS:
        raise MensagemInvalida(f"timestamp mais de 10 min no futuro: {valor}")
    return datetime.fromtimestamp(valor / 1000, tz=timezone.utc)


def validar_posicao(topico: str, conteudo: bytes) -> PosicaoRecebida:
    """Valida uma mensagem de posição inteira (tópico + conteúdo) e devolve os dados convertidos."""
    rota_id, veiculo_id = validar_topico(topico)

    # 1) O conteúdo precisa ser um JSON contendo um objeto { ... }.
    try:
        dados = json.loads(conteudo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise MensagemInvalida(f"conteúdo não é um JSON válido ({erro})") from erro
    if not isinstance(dados, dict):
        raise MensagemInvalida("o JSON deve ser um objeto { ... }")

    # 2) Campos obrigatórios: timestamp e coords com latitude e longitude.
    coords = dados.get("coords")
    if not isinstance(coords, dict):
        raise MensagemInvalida("campo coords ausente ou inválido")
    timestamp = _converter_timestamp(dados.get("timestamp"))
    lat = _coordenada(coords, "latitude", 90)
    lng = _coordenada(coords, "longitude", 180)

    # 3) Campos opcionais: valores inválidos são ignorados.
    horario_id = dados.get("horario_id")
    if not isinstance(horario_id, int) or isinstance(horario_id, bool):
        horario_id = None

    return PosicaoRecebida(
        rota_id=rota_id,
        veiculo_id=veiculo_id,
        timestamp=timestamp,
        lat=lat,
        lng=lng,
        precisao_m=_opcional(coords.get("accuracy"), 0, math.inf),
        velocidade_ms=_opcional(coords.get("speed"), 0, math.inf),
        direcao_graus=_opcional(coords.get("heading"), 0, 360),
        horario_id=horario_id,
    )
