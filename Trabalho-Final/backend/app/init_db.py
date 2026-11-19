"""
Cria no banco as tabelas descritas em app/models.py.

create_all só cria o que ainda não existe: rodar de novo não apaga nem altera nada.
"""

from app import models  # noqa: F401  (importar os modelos registra as tabelas na Base)
from app.core.database import Base, engine


def criar_tabelas() -> None:
    """Cria as tabelas que ainda não existem e mostra quais são."""
    Base.metadata.create_all(engine)
    print("Tabelas prontas:", ", ".join(Base.metadata.tables))


if __name__ == "__main__":
    criar_tabelas()