import grpc
import trab1_pb2
import trab1_pb2_grpc
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup, VerticalGroup, Horizontal
from textual.widgets import Footer, Header, Button, Label, ContentSwitcher, RichLog

FORUNS = {
    1: "Programação",
    2: "Jogos",
    3: "Filmes"
}

class Forum(VerticalGroup):

    def __init__(self, ForumService, id_forum, id_css) -> None:
        super().__init__(id=id_css)
        self.ForumService = ForumService
        self.id_forum = id_forum
        self.forum_name = FORUNS[id_forum]
        self.stream = None

    def compose(self) -> ComposeResult:
        yield ForumWarning(self.forum_name, self.inscrever)
        yield RichLog(markup=False, wrap=True)

    def inscrever(self):
        # evita abrir multiplas inscricoes
        if self.stream is not None:
            return
        
        solicitacao = trab1_pb2.SolicitacaoInscricao(
            id_forum=self.id_forum,
            usuario=trab1_pb2.Usuario(id=1, nome="kauai"),
        )

        try:
            self.stream = self.ForumService.inscrever(solicitacao)
        except grpc.RpcError as error:
            self.notify(str(error), severity="error")
            return

        # remove o warning e escreve no log
        self.query_one(ForumWarning).display = False
        self.query_one(RichLog).write("Aguardando publicações…")
        
        

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

class ForumApp(App):
    CSS_PATH = "trab1_cliente.tcss"

    def __init__(self) -> None:
        # inicializa o serviço que será passado para cada forum
        self.channel = grpc.insecure_channel('localhost:2211')
        self.forum_service_stub = trab1_pb2_grpc.ForumServiceStub(self.channel)
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with VerticalGroup(id="main-layout"):
            with Horizontal(id="menu-buttons"):
                for id_forum, forum in FORUNS.items():
                    yield Button(forum, id=f"open-forum-{id_forum}")
            with ContentSwitcher(initial="forum-1"):
                for id_forum, forum in FORUNS.items():
                    yield Forum(
                        self.forum_service_stub,
                        id_forum,
                        id_css=f"forum-{id_forum}")

    def on_mount(self) -> None:
        self.theme = "tokyo-night"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""

        if button_id.startswith("open-forum-"):
            self.query_one(ContentSwitcher).current = (
                button_id.removeprefix("open-")
            )

if __name__ == "__main__":
    app = ForumApp()
    app.run()
