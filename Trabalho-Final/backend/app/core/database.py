"""
Conexão com o PostgreSQL.

Este módulo é usado pelos dois processos do backend:
- o assinante MQTT, que grava as posições recebidas;
- a API REST, que lê rotas, horários e posições.
Os dois processos não conversam entre si: o banco é o estado compartilhado.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Caminho do arquivo .env: duas pastas acima deste arquivo (core -> app -> backend).
CAMINHO_ENV = Path(__file__).resolve().parents[2] / ".env"

# Lê o .env e coloca os valores nas variáveis de ambiente do processo.
load_dotenv(CAMINHO_ENV)

# Falha cedo, com uma mensagem clara, se faltar alguma variável obrigatória.
for nome in ("DB_NAME", "DB_USER", "DB_PASSWORD"):
    if not os.getenv(nome):
        raise RuntimeError(f"Variável {nome} não definida. Confira o arquivo {CAMINHO_ENV}.")

# Monta o endereço de conexão. URL.create trata com segurança
# caracteres especiais que a senha possa ter.
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",  # PostgreSQL usando o driver psycopg2
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)

# O "engine" administra as conexões com o banco.
# pool_pre_ping=True testa cada conexão antes de usá-la: se o banco reiniciou,
# a conexão morta é descartada em vez de causar erro.
# connect_args: cada conexão do backend usa o fuso UTC. Assim, as datas lidas do banco
# (e devolvidas pela API) vêm sempre em UTC, em qualquer máquina, sem depender do
# fuso configurado no PostgreSQL (está em -03).
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=utc"},
)

# Fábrica de sessões: cada sessão é uma "conversa" com o banco.
# As alterações só são gravadas de fato quando a sessão faz commit.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Classe-mãe de todas as tabelas (os modelos ficarão em app/models.py)."""


def testar_conexao() -> None:
    """Abre uma conexão, pergunta ao banco quem somos e mostra o resultado."""
    with engine.connect() as conexao:
        usuario, banco, versao = conexao.execute(
            text("SELECT current_user, current_database(), version()")
        ).one()
    print(f"Conexão OK: usuário={usuario}, banco={banco}")
    print(versao)


def get_db():
    """
    Fornece uma sessão do banco para cada requisição da API (usada pelo FastAPI com Depends).
    A sessão é fechada ao final da requisição, mesmo que ocorra um erro.
    """
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()


# Permite testar a conexão rodando este arquivo diretamente:
#   python -m app.core.database
if __name__ == "__main__":
    testar_conexao()
