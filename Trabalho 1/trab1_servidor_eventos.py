from concurrent import futures
from datetime import datetime
import grpc
import trab1_pb2
import trab1_pb2_grpc

class ForumServiceServicer(trab1_pb2_grpc.ForumServiceServicer):
    trab1_pb2_grpc.UsuarioForumServiceStub

    def inscrever(self, request, context):
        # TODO: Precisamos armazenar os IPs e portas dos usuários inscritos
        # em cada fórum, para podermos disparar as mensagens para eles.
        ip_porta_usuario = context.peer()

        id_forum = request.id_forum
        timestamp_inscricao = datetime.now().isoformat()

        # TODO: Verificar se o ID do fórum existe e, se sim, recuperar o nome do fórum.
        nome_forum = "Nome do Fórum"

        # TODO: Imprimir algo.

        return trab1_pb2.Forum(
            id_forum = id_forum,
            timestamp_inscricao = timestamp_inscricao,
            nome_forum = nome_forum
        )

    def publicar(self, request, context):
        # TODO: Implementar função para gerar um ID único na hora.
        id_mensagem = 0
        timestamp = datetime.now().isoformat()

        # TODO: Verificar se fórum existe, se usuário existe e é inscrito no fórum,
        # e talvez verificar alguma(s) coisa(s) na mensagem.

        publicacao = trab1_pb2.Publicacao(
            id_mensagem = id_mensagem,
            id_forum = request.id_forum,
            id_usuario = request.id_usuario,
            timestamp = timestamp,
            mensagem = request.mensagem
        )

        # TODO: Fazer um loop disto para cada usuário daquele fórum.
        with grpc.insecure_channel("ip_porta_de_um_usuario") as canal:
            stub_usuario = trab1_pb2_grpc.UsuarioForumServiceStub(canal)
            confirmacao = stub_usuario.enviar(publicacao)

            # TODO: Imprimir algo.

        return trab1_pb2.Confirmacao(
            sucesso = True
        )

def serve():
    servidor_eventos = grpc.server(futures.ThreadPoolExecutor(max_workers = 32))
    trab1_pb2_grpc.add_ForumServiceServicer_to_server(ForumServiceServicer(), servidor_eventos)

    servidor_eventos.add_insecure_port("[::]:2211")
    servidor_eventos.start()
    servidor_eventos.wait_for_termination()

if __name__ == "__main__":
    serve()
