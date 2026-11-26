"""Endereços da API ligados aos ônibus."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Posicao, Veiculo
from app.schemas import PosicaoOut, VeiculoOut

# Todos os endereços deste arquivo começam com /veiculos.
router = APIRouter(prefix="/veiculos", tags=["veiculos"])


@router.get("", response_model=list[VeiculoOut])
def listar_veiculos(db: Session = Depends(get_db)):
    """Lista os ônibus conhecidos pelo backend e se estão online (estado vindo do MQTT)."""
    return db.scalars(select(Veiculo).order_by(Veiculo.id)).all()


@router.get("/{veiculo_id}/posicoes", response_model=list[PosicaoOut])
def historico_do_veiculo(
    veiculo_id: str,
    limite: int = Query(50, ge=1, le=1000, description="Quantidade máxima de posições"),
    db: Session = Depends(get_db),
):
    """Histórico (opcional no escopo): posições mais recentes de um ônibus, da mais nova para 
        a mais antiga."""
    if db.get(Veiculo, veiculo_id) is None:
        raise HTTPException(status_code=404, detail=f"Ônibus não encontrado: {veiculo_id}")
    consulta = (
        select(Posicao)
        .where(Posicao.veiculo_id == veiculo_id)
        .order_by(Posicao.timestamp.desc())
        .limit(limite)
    )
    return db.scalars(consulta).all()
