# Trabalho-Final/backend/app/main.py
"""
API REST do backend (FastAPI): processo separado do assinante MQTT.

A API só LÊ o banco; quem escreve é o assinante. Os dois não conversam
diretamente: o PostgreSQL é o estado compartilhado entre eles.

Documentação interativa: http://localhost:8080/docs
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importar as rotas também importa app.core.database, que carrega o .env.
from app.api import rotas

app = FastAPI(
    title="Cadê o BusUFF? — API",
    description="Rotas, horários, ônibus e posições (Trabalho Final de Sistemas Distribuídos, UFF).",
    version="0.1.0",
)

# CORS: permite que páginas de outra origem (o web app do Kauai, servido em outra
# porta ou máquina) chamem esta API pelo navegador. A lista vem do .env.
# "*" libera qualquer origem; é aceitável aqui porque a API só lê dados
# e não usa login (autenticação está fora do escopo).
origens = [origem.strip() for origem in os.getenv("CORS_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origens,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Registra os grupos de endereços da API.
app.include_router(rotas.router)


@app.get("/", tags=["status"])
def status():
    """Resposta simples para conferir se a API está no ar."""
    return {"servico": "cade-o-busuff-api", "status": "ok"}
