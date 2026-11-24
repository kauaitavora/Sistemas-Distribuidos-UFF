"""
Tabelas do banco de dados, descritas como classes Python (modelos do SQLAlchemy).

Cada classe vira uma tabela, e cada atributo vira uma coluna:
- Rota: rotas pré-fixadas do BusUFF (dados de exemplo);
- Horario: horários de saída de cada rota (opcionais);
- Veiculo: ônibus conhecidos pelo backend e seu estado online/offline (LWT);
- Posicao: cada posição GPS recebida pelo assinante MQTT.
"""

from datetime import datetime, time

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Rota(Base):
    """Rota pré-fixada. O id vai no tópico MQTT: rotas/<rota_id>/<veiculo_id>."""

    __tablename__ = "rota"

    # Id em texto (ex.: "rota-1").
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    origem: Mapped[str] = mapped_column(String(100))
    destino: Mapped[str] = mapped_column(String(100))


class Horario(Base):
    """Horário de saída de uma rota (ex.: 07:30 da rota-1)."""

    __tablename__ = "horario"

    # Id numérico gerado pelo banco; é o "horario_id" que o app pode enviar.
    id: Mapped[int] = mapped_column(primary_key=True)
    rota_id: Mapped[str] = mapped_column(String(32), ForeignKey("rota.id"))
    # Hora local (horário de Brasília), sem data: o mesmo horário vale todos os dias.
    hora_saida: Mapped[time] = mapped_column(Time)

    __table_args__ = (
        # Uma rota não pode ter o mesmo horário cadastrado duas vezes.
        UniqueConstraint("rota_id", "hora_saida", name="uq_horario_rota_hora"),
    )


class Veiculo(Base):
    """Ônibus conhecido pelo backend (cadastrado no seed ou na primeira mensagem)."""

    __tablename__ = "veiculo"

    # Id em texto (ex.: "onibus-01"), igual ao último nível do tópico MQTT.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # Nome opcional: ônibus cadastrados automaticamente chegam só com o id.
    nome: Mapped[str | None] = mapped_column(String(100))
    # Estado vindo do tópico status/<veiculo_id> (online/offline, inclusive o LWT).
    online: Mapped[bool] = mapped_column(default=False)
    # Quando o estado mudou pela última vez (UTC).
    status_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Posicao(Base):
    """Uma leitura de GPS de um ônibus, recebida pelo assinante MQTT."""

    __tablename__ = "posicao"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Rota e ônibus vêm do tópico; o horário é opcional (vem do payload, se existir).
    veiculo_id: Mapped[str] = mapped_column(String(32), ForeignKey("veiculo.id"))
    rota_id: Mapped[str] = mapped_column(String(32), ForeignKey("rota.id"))
    horario_id: Mapped[int | None] = mapped_column(ForeignKey("horario.id"))
    # Momento da leitura do GPS, em UTC (convertido do timestamp em milissegundos do Capacitor).
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    precisao_m: Mapped[float | None] = mapped_column(Float)     # vem de coords.accuracy
    velocidade_ms: Mapped[float | None] = mapped_column(Float)  # vem de coords.speed (m/s)
    direcao_graus: Mapped[float | None] = mapped_column(Float)  # vem de coords.heading
    # Quando o backend gravou a linha (o próprio banco preenche).
    recebido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # Deduplicação: o QoS 1 pode entregar a mesma mensagem mais de uma vez.
        # O banco recusa uma segunda posição com o mesmo ônibus e o mesmo timestamp
        # (princípio fim a fim: a garantia fica na ponta final, não na rede).
        # Esta restrição também cria um índice que acelera a "última posição do ônibus".
        UniqueConstraint("veiculo_id", "timestamp", name="uq_posicao_veiculo_timestamp"),
        # Índice para buscar as posições recentes de uma rota (usado pela API).
        Index("ix_posicao_rota_timestamp", "rota_id", "timestamp"),
    )
