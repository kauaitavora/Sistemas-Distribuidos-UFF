# Trabalho-Final/backend/app/api/rotas.py
"""Endereços da API ligados às rotas de ônibus."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Horario, Rota
from app.schemas import HorarioOut, RotaOut

# Todos os endereços deste arquivo começam com /rotas.
router = APIRouter(prefix="/rotas", tags=["rotas"])


@router.get("", response_model=list[RotaOut])
def listar_rotas(db: Session = Depends(get_db)):
    """Lista as rotas pré-fixadas (usada na tela de escolha do motorista)."""
    return db.scalars(select(Rota).order_by(Rota.id)).all()


@router.get("/{rota_id}/horarios", response_model=list[HorarioOut])
def listar_horarios(rota_id: str, db: Session = Depends(get_db)):
    """Lista os horários de saída de uma rota, em ordem."""
    if db.get(Rota, rota_id) is None:
        # 404 = "não encontrado": a rota pedida não existe.
        raise HTTPException(status_code=404, detail=f"Rota não encontrada: {rota_id}")
    consulta = select(Horario).where(Horario.rota_id == rota_id).order_by(Horario.hora_saida)
    return db.scalars(consulta).all()
