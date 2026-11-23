# Trabalho-Final/backend/app/mqtt/eleicao.py
"""
Eleição de líder entre réplicas do assinante: algoritmo do valentão (bully).

Várias réplicas do assinante recebem as mesmas mensagens (o pub/sub entrega
uma cópia a cada assinante), mas só a LÍDER grava no banco. As outras
(seguidoras) guardam as mensagens dos últimos segundos num buffer, para
assumir sem perder nada se a líder cair.

Base:
- mensagens ELEIÇÃO, OK e COORDENADOR, com tempos limite: vence a réplica viva de maior número, 
  e quem se recupera inicia uma eleição;
- detecção de falha pelo testamento (LWT) de cada processo, no lugar dos heartbeats.

As réplicas não conversam diretamente (MPI); conversam pelo broker. Cada réplica tem uma 
"caixa de entrada" (tópico).

Tópicos (nenhum é retido, para que ninguém receba um líder antigo como atual):
- eleicao/<id>          ELEIÇÃO e OK dirigidos à réplica <id>
- eleicao/coordenador   anúncio do vencedor, para todas
- eleicao/replicas/<id> saída da réplica <id> (LWT, ou aviso ao sair com Ctrl+C)
"""

import json
import threading
import time
from collections import deque

# Tempo que uma réplica espera por um OK depois de mandar ELEIÇÃO.
# Sem OK nesse prazo, nenhuma réplica maior está viva: ela vence.
T_OK = 2.0

# Tempo que uma réplica que recebeu OK espera pelo anúncio do vencedor.
# Se o anúncio não vier (o vencedor caiu no meio), ela recomeça a eleição.
T_COORDENADOR = 5.0

# Quantos segundos de mensagens uma seguidora guarda. Precisa cobrir o tempo de
# detectar a queda da líder (~7,5 s) mais a eleição (~2 s), com folga.
JANELA_BUFFER = 30.0

TOPICO_COORDENADOR = "eleicao/coordenador"
CONTEUDO_SAIDA = json.dumps({"estado": "offline"})


def topico_caixa(replica: int) -> str:
    """Caixa de entrada de uma réplica (recebe ELEIÇÃO e OK)."""
    return f"eleicao/{replica}"


def topico_saida(replica: int) -> str:
    """Tópico onde a saída de uma réplica é avisada (pelo LWT ou por ela mesma)."""
    return f"eleicao/replicas/{replica}"


class Eleicao:
    """Estado e regras do valentão para uma réplica do assinante."""

    def __init__(self, cliente, meu_id: int, total: int, processar):
        """Guarda o cliente MQTT, o número desta réplica, o total de réplicas e a função 
        que grava as mensagens."""
        self.cliente = cliente      # cliente MQTT da réplica (usado para publicar)
        self.meu_id = meu_id        # número desta réplica (1 a total)
        self.total = total          # o valentão exige saber quais ids existem
        self.processar = processar  # função que valida e grava uma mensagem
        self.lider = None           # número da líder atual (None = desconhecida)
        self.em_eleicao = False
        self.recebeu_ok = False
        # Cada eleição ganha um número de rodada. Um temporizador de uma rodada
        # antiga, ao disparar, percebe que a rodada mudou e não faz nada.
        self.rodada = 0
        # As mensagens chegam pela thread do paho e os temporizadores rodam em
        # outras threads: a trava impede que as duas mexam no estado ao mesmo tempo.
        self.trava = threading.Lock()
        self.buffer = deque()  # pares (momento da chegada, mensagem)

    # ------------------------------------------------------------------
    # Ligação com o cliente MQTT
    # ------------------------------------------------------------------

    def registrar_testamento(self) -> None:
        """LWT da réplica: se ela cair sem avisar, o broker publica a saída por ela."""
        self.cliente.will_set(topico_saida(self.meu_id), CONTEUDO_SAIDA, qos=1)

    def topicos(self) -> list[tuple[str, int]]:
        """Tópicos que a réplica assina, além das posições e dos status."""
        return [
            (topico_caixa(self.meu_id), 1),
            (TOPICO_COORDENADOR, 1),
            ("eleicao/replicas/+", 1),
        ]

    def avisar_saida(self):
        """
        Saída normal (Ctrl+C): avisa as outras, já que um DISCONNECT não dispara o LWT.
        Devolve o comprovante da publicação, para quem chamou poder esperar o PUBACK.
        """
        return self.cliente.publish(topico_saida(self.meu_id), CONTEUDO_SAIDA, qos=1)

    def sou_lider(self) -> bool:
        """True se esta réplica é a líder atual (consulta protegida pela trava)."""
        with self.trava:
            return self.lider == self.meu_id

    def deve_processar(self, mensagem) -> bool:
        """
        Chamada para cada posição ou status recebido.
        Líder: devolve True (a mensagem é gravada normalmente).
        Seguidora: guarda a mensagem no buffer e devolve False.
        A decisão e o armazenamento acontecem sob a mesma trava, para que
        nenhuma mensagem se perca no instante em que a réplica vira líder.
        """
        agora = time.monotonic()
        with self.trava:
            if self.lider == self.meu_id:
                return True
            self.buffer.append((agora, mensagem))
            # Descarta o que for mais antigo que a janela.
            while self.buffer and agora - self.buffer[0][0] > JANELA_BUFFER:
                self.buffer.popleft()
            return False

    def tratar(self, mensagem) -> None:
        """Trata uma mensagem de um tópico eleicao/... (sem nunca derrubar o assinante)."""
        try:
            dados = json.loads(mensagem.payload.decode("utf-8"))
            partes = mensagem.topic.split("/")
            if mensagem.topic == TOPICO_COORDENADOR:
                self._ao_receber_coordenador(dados)
            elif len(partes) == 3 and partes[1] == "replicas":
                self._ao_saber_de_saida(int(partes[2]))
            elif len(partes) == 2:
                self._ao_receber_na_caixa(dados)
        except Exception as erro:
            print(f"[ELEIÇÃO] mensagem inválida em {mensagem.topic}: {erro!r}")

    # ------------------------------------------------------------------
    # Algoritmo do valentão
    # ------------------------------------------------------------------

    def iniciar_eleicao(self, motivo: str) -> None:
        """Manda ELEIÇÃO para todas as réplicas de número maior e espera OK."""
        with self.trava:
            if self.em_eleicao:
                return  # já há uma eleição em andamento nesta réplica
            self.em_eleicao = True
            self.recebeu_ok = False
            self.rodada += 1
            rodada = self.rodada
        print(f"[ELEIÇÃO] réplica {self.meu_id} inicia eleição ({motivo})")
        for outra in range(self.meu_id + 1, self.total + 1):
            self._enviar(outra, "ELEICAO")
        # Tempo limite para os OKs (o valentão presume um sistema síncrono).
        threading.Timer(T_OK, self._fim_espera_ok, args=(rodada,)).start()

    def _fim_espera_ok(self, rodada: int) -> None:
        """Fim do tempo limite T_OK: sem OK, esta réplica vence; com OK, passa a esperar 
        o anúncio do vencedor."""
        with self.trava:
            if rodada != self.rodada or not self.em_eleicao:
                return  # rodada antiga: algo já mudou
            if self.recebeu_ok:
                # Uma réplica maior está viva: ela é que deve vencer.
                threading.Timer(T_COORDENADOR, self._fim_espera_coordenador, args=(rodada,)).start()
                aguardar = True
            else:
                aguardar = False
        if aguardar:
            print(f"[ELEIÇÃO] réplica {self.meu_id} recebeu OK; aguardando o anúncio do vencedor")
        else:
            self._virar_lider()

    def _fim_espera_coordenador(self, rodada: int) -> None:
        """Fim do tempo limite T_COORDENADOR: se o vencedor não se anunciou (pode ter caído), 
        recomeça a eleição."""
        with self.trava:
            if rodada != self.rodada or not self.em_eleicao:
                return  # o anúncio chegou a tempo
            self.em_eleicao = False
        self.iniciar_eleicao("o anúncio do vencedor não chegou")

    def _virar_lider(self) -> None:
        """Nenhuma réplica maior respondeu: esta vence, anuncia e grava o que guardou."""
        with self.trava:
            self.lider = self.meu_id
            self.em_eleicao = False
            self.rodada += 1
            # Só o que chegou dentro da janela: se ficou muito tempo sem chegar
            # mensagem nova, o buffer ainda pode ter mensagens antigas
            # (a limpeza em deve_processar só roda quando chega mensagem).
            limite = time.monotonic() - JANELA_BUFFER
            pendentes = [item for item in self.buffer if item[0] >= limite]
            self.buffer.clear()
        self.cliente.publish(TOPICO_COORDENADOR, json.dumps({"lider": self.meu_id}), qos=1)
        print(f"[ELEIÇÃO] réplica {self.meu_id} é a nova LÍDER; gravando {len(pendentes)} mensagem(ns) do buffer")
        # O que a líder anterior já tinha gravado vira [DUPLICADA]: a restrição
        # única do banco garante que nada é gravado duas vezes (idempotência).
        for _, mensagem in pendentes:
            self.processar(mensagem)

    def _ao_receber_na_caixa(self, dados: dict) -> None:
        """Trata ELEIÇÃO (de uma réplica menor: responde OK e disputa no lugar dela) e 
        OK (uma réplica maior está viva)."""
        tipo, de = dados.get("tipo"), dados.get("de")
        if not isinstance(de, int):
            raise ValueError(f"campo 'de' inválido: {de!r}")
        if tipo == "ELEICAO" and de < self.meu_id:
            # Uma réplica menor quer ser líder: esta, que é maior e está viva,
            # responde OK (para ela parar) e disputa a eleição no lugar dela.
            print(f"[ELEIÇÃO] réplica {self.meu_id} recebeu ELEIÇÃO de {de}; respondendo OK")
            self._enviar(de, "OK")
            self.iniciar_eleicao(f"pedido da réplica {de}")
        elif tipo == "OK":
            with self.trava:
                if self.em_eleicao:
                    self.recebeu_ok = True
            print(f"[ELEIÇÃO] réplica {self.meu_id} recebeu OK de {de}")

    def _ao_receber_coordenador(self, dados: dict) -> None:
        """Trata o anúncio do vencedor: aceita se ele for maior; se for menor, inicia 
        nova eleição (valentão)."""
        novo = dados.get("lider")
        if not isinstance(novo, int):
            raise ValueError(f"campo 'lider' inválido: {novo!r}")
        if novo == self.meu_id:
            return  # é o nosso próprio anúncio (quem assina um tópico recebe o que publica)
        if novo > self.meu_id:
            with self.trava:
                self.lider = novo
                self.em_eleicao = False
                self.rodada += 1
            print(f"[ELEIÇÃO] réplica {novo} é a líder; réplica {self.meu_id} segue como SEGUIDORA")
        else:
            # Uma réplica menor se anunciou, mas esta é maior e está viva: "valentão".
            self.iniciar_eleicao(f"réplica {novo} se anunciou, mas {self.meu_id} é maior")

    def _ao_saber_de_saida(self, replica: int) -> None:
        """Uma réplica saiu (LWT ou aviso de saída): se era a líder, inicia uma eleição."""
        if replica == self.meu_id:
            return  # aviso antigo sobre esta própria réplica
        print(f"[ELEIÇÃO] réplica {replica} saiu")
        with self.trava:
            era_lider = replica == self.lider
        if era_lider:
            self.iniciar_eleicao(f"a líder {replica} caiu")

    def _enviar(self, destino: int, tipo: str) -> None:
        """Publica ELEIÇÃO ou OK na caixa de entrada de outra réplica."""
        conteudo = json.dumps({"tipo": tipo, "de": self.meu_id})
        self.cliente.publish(topico_caixa(destino), conteudo, qos=1)
