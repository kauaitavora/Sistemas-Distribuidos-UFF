# Trabalho-Final/backend/app/mqtt/gravacao.py
"""
Gravação das posições validadas no PostgreSQL.

Regras que dependem do banco:
- a rota precisa existir (as rotas são pré-fixadas);
- um ônibus desconhecido é cadastrado automaticamente;
- um horario_id inexistente ou de outra rota é ignorado;
- uma posição repetida (mesmo ônibus e mesmo timestamp) não é gravada de novo.
"""

from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import Horario, Posicao, Rota, Veiculo
from app.mqtt.validacao import MensagemInvalida, PosicaoRecebida


def gravar_posicao(posicao: PosicaoRecebida) -> bool:
    """
    Grava a posição no banco, numa única transação (tudo ou nada).
    Devolve True se gravou e False se a posição era duplicada.
    Levanta MensagemInvalida se a rota não existir.
    """
    with SessionLocal.begin() as sessao:
        # 1) As rotas são pré-fixadas: posição de rota desconhecida é recusada.
        #    (O erro desfaz a transação inteira: nada é gravado.)
        if sessao.get(Rota, posicao.rota_id) is None:
            raise MensagemInvalida(f"rota inexistente: {posicao.rota_id}")

        # 2) Ônibus: cadastra se for novo; se estava offline, a posição o reativa.
        #    INSERT ... ON CONFLICT DO UPDATE ... WHERE online = false:
        #    - ônibus novo: é inserido já online;
        #    - ônibus offline: passa a online, e status_em registra a mudança;
        #    - ônibus já online: nada muda (evita uma escrita a cada segundo).
        agora = datetime.now(timezone.utc)
        sessao.execute(
            insert(Veiculo)
            .values(id=posicao.veiculo_id, online=True, status_em=agora)
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"online": True, "status_em": agora},
                where=Veiculo.online.is_(False),
            )
        )

        # 3) Horário opcional: se não existir ou for de outra rota, é ignorado.
        horario_id = posicao.horario_id
        if horario_id is not None:
            horario = sessao.get(Horario, horario_id)
            if horario is None or horario.rota_id != posicao.rota_id:
                print(f"[AVISO] horario_id {horario_id} ignorado (inexistente ou de outra rota)")
                horario_id = None

        # 4) Posição: INSERT ... ON CONFLICT DO NOTHING na restrição única
        #    (veiculo_id, timestamp). Se a mensagem for repetida (QoS 1), o banco
        #    ignora a segunda cópia, e o RETURNING não devolve nenhuma linha.
        id_gravado = sessao.execute(
            insert(Posicao)
            .values(
                veiculo_id=posicao.veiculo_id,
                rota_id=posicao.rota_id,
                horario_id=horario_id,
                timestamp=posicao.timestamp,
                lat=posicao.lat,
                lng=posicao.lng,
                precisao_m=posicao.precisao_m,
                velocidade_ms=posicao.velocidade_ms,
                direcao_graus=posicao.direcao_graus,
            )
            .on_conflict_do_nothing(index_elements=["veiculo_id", "timestamp"])
            .returning(Posicao.id)
        ).scalar_one_or_none()

    # Saindo do "with", a transação recebe o commit.
    return id_gravado is not None
