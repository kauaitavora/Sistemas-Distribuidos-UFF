from concurrent import futures
from datetime import datetime
from queue import Queue, Empty
from threading import Lock

import grpc
import trab1_pb2
import trab1_pb2_grpc


# Fóruns disponíveis na aplicação.
# Como criação/remoção de fóruns não faz parte do escopo do trabalho,
# utilizaremos alguns fóruns previamente definidos.
FORUNS = {
    1: "Programação",
    2: "Jogos",
    3: "Filmes"
}


class ForumServiceServicer(trab1_pb2_grpc.ForumServiceServicer):
    def __init__(self):

        # Estrutura:
        #
        # {
        #     id_forum: {
        #         id_usuario: Queue()
        #     }
        # }
        #
        # Cada Queue representa o fluxo de mensagens que será
        # enviado para um usuário inscrito naquele fórum.
        self.assinantes = {}

        # Contador simples para gerar IDs únicos para as mensagens
        # enquanto o servidor estiver em execução.
        self.proximo_id_mensagem = 1

        # Protege as estruturas compartilhadas contra acessos
        # concorrentes feitos por diferentes clientes.
        self.lock = Lock()

    def inscrever(self, request, context):
        id_forum = request.id_forum
        usuario = request.usuario
        id_usuario = usuario.id

        # Verifica se o fórum solicitado existe.
        if id_forum not in FORUNS:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                "Fórum não encontrado."
            )

        # Cada assinatura possui sua própria fila.
        fila_usuario = Queue()

        # Registra o usuário como assinante do fórum.
        with self.lock:
            if id_forum not in self.assinantes:
                self.assinantes[id_forum] = {}

            self.assinantes[id_forum][id_usuario] = fila_usuario

        print(
            f"[INSCRIÇÃO] Usuário {usuario.nome} "
            f"(ID {id_usuario}) inscrito em "
            f"{FORUNS[id_forum]} (ID {id_forum})"
        )

        try:
            # A chamada permanece ativa enquanto o cliente estiver conectado.
            while context.is_active():
                try:
                    # Aguarda alguma publicação destinada a este assinante.
                    publicacao = fila_usuario.get(timeout=1)

                    # Cada yield envia uma nova resposta pelo stream gRPC.
                    yield publicacao

                except Empty:
                    # Nenhuma publicação chegou neste intervalo.
                    # O loop continua para que seja possível verificar
                    # se o cliente ainda está conectado.
                    continue

        finally:
            # Remove a assinatura quando o cliente encerra o stream
            # ou perde a conexão.
            with self.lock:
                assinantes_forum = self.assinantes.get(id_forum)

                if (
                    assinantes_forum is not None
                    and assinantes_forum.get(id_usuario) is fila_usuario
                ):
                    del assinantes_forum[id_usuario]

                    if not assinantes_forum:
                        del self.assinantes[id_forum]

            print(
                f"[DESCONEXÃO] Usuário {usuario.nome} "
                f"(ID {id_usuario}) saiu de "
                f"{FORUNS[id_forum]} (ID {id_forum})"
            )

    def publicar(self, request, context):
        id_forum = request.id_forum
        id_usuario = request.id_usuario
        nome_usuario = request.nome_usuario
        mensagem = request.mensagem.strip()

        # Verifica se o fórum existe.
        if id_forum not in FORUNS:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                "Fórum não encontrado."
            )

        # Evita publicações vazias.
        if not mensagem:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "A mensagem não pode estar vazia."
            )

        with self.lock:
            assinantes_forum = self.assinantes.get(id_forum)

            # Nesta aplicação, o usuário precisa estar inscrito
            # no fórum para publicar nele.
            if (
                assinantes_forum is None
                or id_usuario not in assinantes_forum
            ):
                context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    "O usuário precisa estar inscrito no fórum para publicar."
                )

            # Gera um ID único para esta execução do servidor.
            id_mensagem = self.proximo_id_mensagem
            self.proximo_id_mensagem += 1

            # Faz uma cópia das filas atuais para não manter
            # o lock durante a distribuição das mensagens.
            filas_destino = list(assinantes_forum.values())

        timestamp = datetime.now().isoformat()

        publicacao = trab1_pb2.Publicacao(
            id_mensagem=id_mensagem,
            id_forum=id_forum,
            id_usuario=id_usuario,
            timestamp=timestamp,
            mensagem=mensagem,
            nome_usuario=nome_usuario
        )

        # Distribui o evento a todos os assinantes do fórum.
        for fila_usuario in filas_destino:
            fila_usuario.put(publicacao)

        print(
            f"[PUBLICAÇÃO] Mensagem {id_mensagem} "
            f"publicada por {nome_usuario} (ID {id_usuario}) em "
            f"{FORUNS[id_forum]} (ID {id_forum}) "
            f"para {len(filas_destino)} assinante(s)."
        )

        return trab1_pb2.Confirmacao(
            sucesso=True
        )
    

def serve():
    servidor_eventos = grpc.server(
        futures.ThreadPoolExecutor(max_workers=32)
    )

    trab1_pb2_grpc.add_ForumServiceServicer_to_server(
        ForumServiceServicer(),
        servidor_eventos
    )

    servidor_eventos.add_insecure_port("[::]:2211")
    servidor_eventos.start()

    print("Servidor de eventos ativo na porta 2211.")

    servidor_eventos.wait_for_termination()


if __name__ == "__main__":
    serve()
