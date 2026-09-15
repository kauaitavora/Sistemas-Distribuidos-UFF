import argparse
import grpc
import trab1_pb2
import trab1_pb2_grpc
from datetime import datetime
from textual import work
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup, VerticalGroup, Horizontal
from textual.widgets import Footer, Header, Button, Label, ContentSwitcher, RichLog, Input

FORUNS = {
    1: "Programação",
    2: "Jogos",
    3: "Filmes"
}

class Forum(VerticalGroup):

    def __init__(self, ForumService, id_forum, usuario, id_css) -> None:
        super().__init__(id=id_css)
        self.ForumService = ForumService
        self.id_forum = id_forum
        self.usuario = usuario
        self.forum_name = FORUNS[id_forum]
        self.stream = None

    def compose(self) -> ComposeResult:
        yield ForumWarning(self.forum_name, self.inscrever)
        yield RichLog(markup=False, wrap=True)
        yield ForumMessage(self.publicar, disabled=True)

    def inscrever(self):
        # evita abrir multiplas inscricoes
        if self.stream is not None:
            return
        
        solicitacao = trab1_pb2.SolicitacaoInscricao(
            id_forum=self.id_forum,
            usuario= self.usuario,
        )

        try:
            self.stream = self.ForumService.inscrever(solicitacao)
        except grpc.RpcError as error:
            self.erro_inscricao(error.details() or str(error))
            return

        # remove o warning, mostra o input e pega as publicacoes
        self.query_one(ForumWarning).display = False
        self.query_one(ForumMessage).disabled = False
        self.get_publicacoes()

    @work(thread=True)
    def publicar(self, message):
        solicitacao = trab1_pb2.SolicitacaoPublicacao(
            id_forum = self.id_forum,
            id_usuario = self.usuario.id,
            mensagem = message,
            nome_usuario = self.usuario.nome
        )

        try:
            confirmacao = self.ForumService.publicar(solicitacao)
            if confirmacao.sucesso:
                self.app.call_from_thread(
                    self.publicacao_confirmada
                )
        except grpc.RpcError as error:
            self.app.call_from_thread(
                self.notify,
                error.details() or str(error),
                severity="error",
            )

    @work(thread=True)
    def get_publicacoes(self):
        try:
            for publicacao in self.stream:
                self.app.call_from_thread(
                    self.exibir_publicacao,
                    publicacao
                )
        except grpc.RpcError as error:
            self.app.call_from_thread(
                self.erro_inscricao,
                error.details() or str(error)
            )

    def exibir_publicacao(self, publicacao):
        self.query_one(RichLog).write(
            f"{publicacao.nome_usuario}: "
            f"{publicacao.mensagem}"
        )

    def erro_inscricao(self, error):
        self.stream = None
        self.query_one(ForumWarning).display = True
        self.notify(error, severity="error")

    def publicacao_confirmada(self) -> None:
        self.query_one(ForumMessage).clear()

    def on_unmount(self) -> None:
        if self.stream is not None:
            self.stream.cancel()


class ForumWarning(VerticalGroup):

    def __init__(self, forum_name, inscrever) -> None:
        self.inscrever = inscrever
        self.forum_name = forum_name
        super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(f"Você ainda não está inscrito no fórum '{self.forum_name}'")
        with Horizontal():
            yield Button("Inscrever-se", id="subscribe", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # realiza a inscrição e remove o aviso
        if event.button.id == "subscribe":
            event.stop()
            self.inscrever()

class ForumMessage(Input):
    
    def __init__(self, publicar, disabled):
        super().__init__(disabled=disabled)
        self.publicar = publicar

    def on_input_submitted(self):
        self.publicar(self.value)
        


class ForumApp(App):
    CSS_PATH = "trab1_cliente.tcss"

    def __init__(self) -> None:
        # inicializa o serviço que será passado para cada forum
        self.channel = grpc.insecure_channel('localhost:2211')
        self.forum_service_stub = trab1_pb2_grpc.ForumServiceStub(self.channel)
        self.usuario = self.get_usuario()
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with VerticalGroup(id="main-layout"):
            with Horizontal(id="menu-buttons"):
                for id_forum, forum in FORUNS.items():
                    yield Button(forum, id=f"open-forum-{id_forum}", classes="forum-buttons")
            with ContentSwitcher(initial="forum-1"):
                for id_forum, forum in FORUNS.items():
                    yield Forum(
                        self.forum_service_stub,
                        id_forum,
                        self.usuario,
                        id_css=f"forum-{id_forum}")

    def on_mount(self) -> None:
        self.theme = "tokyo-night"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""

        if button_id.startswith("open-forum-"):
            self.query_one(ContentSwitcher).current = (
                button_id.removeprefix("open-")
            )

    def get_usuario(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("id", type=int)
        parser.add_argument("nome")
        args = parser.parse_args()

        return trab1_pb2.Usuario(
            id=args.id,
            nome=args.nome,
        )


if __name__ == "__main__":
    app = ForumApp()
    app.run()
