"""
Dados iniciais (seed) do banco: rotas, horários e ônibus de EXEMPLO.

Pode ser rodado várias vezes: o que já existe não é inserido de novo.
"""

from datetime import time

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.init_db import criar_tabelas
from app.models import Horario, Rota, Veiculo

# Rotas de exemplo. O "id" segue o formato do contrato e vai no tópico MQTT.
ROTAS = [
    {"id": "rota-1", "nome": "Rota 1", "origem": "Campus", "destino": "Centro"},
    {"id": "rota-2", "nome": "Rota 2", "origem": "Campus", "destino": "Rodoviária"},
    {"id": "rota-3", "nome": "Rota 3", "origem": "Centro", "destino": "Rodoviária"},
]

# Horários de saída de exemplo (hora local), os mesmos para as três rotas.
HORAS_SAIDA = [time(7, 0), time(12, 0), time(17, 30)]

# Um ônibus por rota. Todos começam offline; o estado muda com as mensagens de status.
# Ônibus novos também podem ser cadastrados pelo assinante, na primeira mensagem.
VEICULOS = [
    {"id": "onibus-01", "nome": "Ônibus 01", "online": False},
    {"id": "onibus-02", "nome": "Ônibus 02", "online": False},
    {"id": "onibus-03", "nome": "Ônibus 03", "online": False},
]


def popular_banco() -> None:
    """Insere os dados de exemplo que ainda não existem no banco."""
    criar_tabelas()  # garante que as tabelas existem antes de inserir

    # Combina cada rota com cada horário: 3 rotas x 3 horários = 9 linhas.
    horarios = [
        {"rota_id": rota["id"], "hora_saida": hora}
        for rota in ROTAS
        for hora in HORAS_SAIDA
    ]

    # Uma única transação: ou grava tudo, ou nada (se der erro no meio).
    with SessionLocal.begin() as sessao:
        # INSERT ... ON CONFLICT DO NOTHING (recurso do PostgreSQL):
        # se a linha já existir, o banco simplesmente a ignora, sem erro.
        # É a mesma técnica que o assinante MQTT vai usar contra mensagens duplicadas.
        sessao.execute(
            insert(Rota).values(ROTAS).on_conflict_do_nothing(index_elements=["id"])
        )
        sessao.execute(
            insert(Veiculo).values(VEICULOS).on_conflict_do_nothing(index_elements=["id"])
        )
        sessao.execute(
            insert(Horario)
            .values(horarios)
            .on_conflict_do_nothing(index_elements=["rota_id", "hora_saida"])
        )

    # Mostra quantas linhas cada tabela tem agora (o número deve ser o mesmo a cada execução).
    with SessionLocal() as sessao:
        for modelo in (Rota, Horario, Veiculo):
            total = sessao.scalar(select(func.count()).select_from(modelo))
            print(f"{modelo.__tablename__}: {total} linha(s)")


if __name__ == "__main__":
    popular_banco()