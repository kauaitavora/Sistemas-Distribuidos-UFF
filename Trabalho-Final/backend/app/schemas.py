"""
Formatos das respostas da API (modelos do Pydantic).

Separam o que a API devolve (o contrato com os apps) da estrutura interna do banco
(app/models.py): podemos mudar uma tabela sem mudar a resposta, e vice-versa.
"""

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict


class RotaOut(BaseModel):
    """Rota pré-fixada, como aparece na tela de escolha do motorista."""

    # from_attributes=True permite montar a resposta direto de um objeto do SQLAlchemy.
    model_config = ConfigDict(from_attributes=True)

    id: str
    nome: str
    origem: str
    destino: str


class HorarioOut(BaseModel):
    """Horário de saída de uma rota (hora local)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rota_id: str
    hora_saida: time


class VeiculoOut(BaseModel):
    """Ônibus conhecido pelo backend e seu estado (online/offline vem do MQTT)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    nome: str | None
    online: bool
    status_em: datetime | None


class PosicaoOut(BaseModel):
    """Posição de um ônibus, com data e hora em UTC."""

    model_config = ConfigDict(from_attributes=True)

    veiculo_id: str
    rota_id: str
    horario_id: int | None
    timestamp: datetime
    lat: float
    lng: float
    precisao_m: float | None
    velocidade_ms: float | None
    direcao_graus: float | None
