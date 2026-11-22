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

from sqlalchemy import update
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
    agora = datetime.now(timezone.utc)
    with SessionLocal.begin() as sessao:
        # 1) As rotas são pré-fixadas: posição de rota desconhecida é recusada.
        #    (O erro desfaz a transação inteira: nada é gravado.)
        if sessao.get(Rota, posicao.rota_id) is None:
            raise MensagemInvalida(f"rota inexistente: {posicao.rota_id}")

        # 2) Ônibus novo: cadastra já como online. Se já existe, nada muda AQUI;
        #    reativar um ônibus offline fica para o passo 5, depois de sabermos
        #    se a posição é nova ou repetida.
        sessao.execute(
            insert(Veiculo)
            .values(id=posicao.veiculo_id, online=True, status_em=agora)
            .on_conflict_do_nothing(index_elements=["id"])
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

        # 5) Só uma posição NOVA reativa um ônibus offline. Uma cópia repetida é
        #    uma mensagem antiga (reentrega do QoS 1, sessão persistente ou buffer
        #    da nova líder) e não pode desfazer um "offline" mais recente, como o
        #    LWT de um celular que caiu. Assim, receber a mesma posição duas vezes
        #    tem exatamente o mesmo efeito que recebê-la uma vez (idempotência).
        if id_gravado is not None:
            sessao.execute(
                update(Veiculo)
                .where(Veiculo.id == posicao.veiculo_id, Veiculo.online.is_(False))
                .values(online=True, status_em=agora)
            )

    # Saindo do "with", a transação recebe o commit.
    return id_gravado is not None


def gravar_status(veiculo_id: str, online: bool) -> bool:
    """
    Atualiza o estado online/offline de um ônibus (tópico status/<veiculo_id>, inclusive o LWT).
    Cadastra o ônibus se for novo. Devolve True se o estado mudou.
    """
    agora = datetime.now(timezone.utc)
    with SessionLocal.begin() as sessao:
        # INSERT ... ON CONFLICT DO UPDATE ... WHERE online IS DISTINCT FROM <novo estado>:
        # só escreve quando o estado muda. Mensagens repetidas (QoS 1) ou retidas (retain)
        # não alteram nada, ou seja, a operação é idempotente.
        # O RETURNING devolve uma linha só quando houve inserção ou mudança.
        id_alterado = sessao.execute(
            insert(Veiculo)
            .values(id=veiculo_id, online=online, status_em=agora)
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"online": online, "status_em": agora},
                where=Veiculo.online.is_distinct_from(online),
            )
            .returning(Veiculo.id)
        ).scalar_one_or_none()
    return id_alterado is not None
