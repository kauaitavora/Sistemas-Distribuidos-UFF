<!-- Trabalho-Final/backend/CONTRATO.md -->
# Contrato de mensagens MQTT — Cadê o BusUFF?

> **Status: PROPOSTA (v0.3)**, ajustada com as respostas do João (16/11 e 18/11). Itens marcados com **[A VALIDAR]** dependem de decisão do grupo.

## 1. Visão geral

App do motorista → publica a posição → HiveMQ → web app dos alunos (mapa) e assinante do backend (grava no PostgreSQL).

| Conexão | Quem usa | Endereço |
|---|---|---|
| WebSocket | apps (navegador e Capacitor) | `ws://<host>:8000/mqtt` |
| TCP | assinante do backend | `<host>:1883` |

`<host>` é o endereço da máquina onde o broker roda. `localhost` só funciona quando o cliente está no mesmo computador do broker; no celular, é preciso usar o IP da máquina na rede.

**Broker:** HiveMQ CE, versão estável mais recente (testado com a 2026.5). Para testes, qualquer broker com TCP na porta 1883 e WebSocket na porta 8000, no caminho `/mqtt`, também funciona (ex.: Mosquitto). Na apresentação, usaremos o HiveMQ, que é o citado na proposta.

**Onde roda:** por enquanto, broker, backend e banco rodam nas máquinas do grupo.

## 2. Tópicos

| Tópico | Quem publica | Quem assina | QoS | Retain |
|---|---|---|---|---|
| `rotas/<rota_id>/<veiculo_id>` | app do motorista | web app (`rotas/#` ou `rotas/<rota_id>/+`) e backend (`rotas/+/+`) | 1 | não |
| `status/<veiculo_id>` | app do motorista (online/offline) e broker (LWT) | backend (`status/+`) e web app (opcional) | 1 | sim |

O tópico é a **única fonte** da rota e do ônibus: o backend lê `rota_id` e `veiculo_id` dos níveis do tópico, e o conteúdo da mensagem não precisa repeti-los. A barra separa rota e ônibus e permite assinar todos os ônibus de uma rota com `rotas/<rota_id>/+`.

Regras para `rota_id` e `veiculo_id`:
- apenas letras minúsculas sem acento, números e hífen (ex.: `rota-1`, `onibus-03`), com até 32 caracteres;
- nunca usar `/`, `+`, `#` ou espaço, que são caracteres especiais do MQTT;
- `rota_id` deve ser uma das rotas pré-fixadas, listadas pela API (seção 6);
- um `veiculo_id` que o backend ainda não conhece é cadastrado automaticamente na primeira mensagem.

O tópico de status fica **fora** de `rotas/` de propósito: quem assina `rotas/#` recebe só posições.

## 3. Mensagem de posição

Publicada em `rotas/<rota_id>/<veiculo_id>` a cada 1 s enquanto a viagem estiver ativa. O conteúdo é o objeto `Position` do plugin de geolocalização do Capacitor, serializado em JSON sem alterações (`JSON.stringify(position)`), como o app já faz hoje.

Exemplo:

```json
{
  "timestamp": 1795170605123,
  "coords": {
    "latitude": -22.505253,
    "longitude": -41.920643,
    "accuracy": 12.5,
    "altitude": null,
    "altitudeAccuracy": null,
    "speed": 8.3,
    "heading": 90.0
  }
}
```

(`1795170605123` corresponde a 20/11/2026, 10:30:05.123 em UTC.)

Campos que o backend lê:

| Campo | Tipo | Obrigatório | Uso no backend |
|---|---|---|---|
| `timestamp` | número (milissegundos desde 01/01/1970, UTC) | sim | convertido em data e hora UTC; junto com o ônibus, identifica a posição |
| `coords.latitude` / `coords.longitude` | número (graus decimais) | sim | colunas `lat` (−90 a 90) e `lng` (−180 a 180) |
| `coords.accuracy` | número ou `null` | não | coluna `precisao_m` (metros) |
| `coords.speed` | número ou `null` | não | coluna `velocidade_ms` (**m/s**) |
| `coords.heading` | número ou `null` | não | coluna `direcao_graus` (0 a 360, a partir do norte) |
| `horario_id` | inteiro ou `null` | não | horário escolhido pelo motorista, se o app enviar (campo extra, fora de `coords`) |

Outros campos (como `altitude`) são aceitos e ignorados.

Se o app passar a enviar `horario_id`, o objeto deve ser montado campo a campo (`{ timestamp: position.timestamp, coords: { latitude: position.coords.latitude, ... }, horario_id }`). Copiar com `{ ...position }` pode gerar um objeto vazio no navegador, onde a posição é um objeto do próprio navegador.

## 4. Mensagem de status (online/offline e LWT)

Publicada em `status/<veiculo_id>`, com QoS 1 e **retain = true**, para que quem se conectar depois saiba o estado atual. O backend usa o `veiculo_id` do tópico.

```json
{ "veiculo_id": "onibus-01", "estado": "online" }
```

O campo `estado` vale `"online"` ou `"offline"`.

Ciclo de vida:
1. **Ao conectar**, o app registra o testamento (LWT) com `{"veiculo_id": "...", "estado": "offline"}` e, em seguida, publica `"online"`.
2. **Ao encerrar a viagem normalmente**, o app publica `"offline"` e só depois desconecta. Uma desconexão normal **não** dispara o LWT.
3. **Se o app cair** (sem sinal, sem bateria ou fechado à força), o broker percebe a falta de comunicação depois de cerca de 1,5 × `keepalive` e publica o LWT `"offline"` no lugar do app.

Recomendação: `keepalive` de 15 s, o que detecta a queda em cerca de 22 s. Com o padrão do mqtt.js (60 s), a detecção levaria cerca de 90 s.

Exemplo de referência para o app (mqtt.js):

```js
mqtt.connect(url, {
  keepalive: 15,
  will: {
    topic: `status/${veiculoId}`,
    payload: JSON.stringify({ veiculo_id: veiculoId, estado: "offline" }),
    qos: 1,
    retain: true,
  },
});
```

## 5. Como o backend trata as mensagens

- **Inválida** (JSON quebrado, `timestamp` ou coordenadas ausentes ou fora da faixa, tópico fora do formato `rotas/<rota_id>/<veiculo_id>`, rota inexistente): é descartada e registrada em log, sem derrubar o assinante.
- **Ônibus novo**: um `veiculo_id` com formato válido que o banco ainda não conhece é cadastrado automaticamente. Assim, funciona tanto se o motorista escolher o ônibus numa lista quanto se o app usar um código fixo por rota.
- **Horário inválido**: um `horario_id` que não existe ou é de outra rota é ignorado (a posição é gravada sem horário) e registrado em log.
- **Duplicada**: com QoS 1, a mesma mensagem pode chegar mais de uma vez. O backend considera duplicada a posição com o mesmo ônibus (do tópico) e o mesmo `timestamp`, e grava apenas uma.
- **Status**: `offline` marca o ônibus como fora de serviço; uma nova posição ou um `online` o reativa.

## 6. API REST do backend (prévia; detalhes na Etapa 4)

Porta **8080**. Rotas previstas:
- `GET /rotas`: rotas disponíveis
- `GET /rotas/{rota_id}/horarios`: horários de uma rota
- `GET /veiculos`: ônibus conhecidos pelo backend
- `GET /rotas/{rota_id}/posicoes/ultima`: última posição de cada ônibus da rota (até 10 minutos atrás)

## 7. Decisões

Decidido em 16/11 e 18/11 (respostas do João):
- as rotas são pré-fixadas, e o motorista escolhe uma da lista; enquanto não houver a lista oficial, o backend cria rotas de exemplo;
- o horário é opcional, com dados de exemplo enquanto não houver horários oficiais;
- o tópico é `rotas/<rota_id>/<veiculo_id>` (rota e ônibus separados por barra);
- o payload segue o formato do plugin do Capacitor, sem alterações, enviado a cada 1 s;
- ônibus novos são cadastrados automaticamente pelo backend;
- tudo roda nas máquinas do grupo por enquanto;
- o broker é o HiveMQ CE (o Mosquitto serve para testes locais).

Em aberto, sem bloquear o backend:
1. **Como o app define o código do ônibus** [A VALIDAR]: escolha numa lista ou código fixo por rota.

## 8. Mudanças necessárias nos apps (resumo)

- **João**: publicar em `rotas/<rota_id>/<veiculo_id>` (hoje é `rotas/<rota>`), com QoS 1; manter o payload como está; configurar o LWT e o `keepalive` (seção 4); tornar o endereço do broker configurável.
- **Kauai**: usar um marcador por ônibus, com o `veiculo_id` do tópico (terceiro nível) como chave; a leitura de `coords.latitude` e `coords.longitude` continua igual; criar a tela de escolha de rota consumindo a API.

## 9. Fora do escopo

Autenticação e criptografia (TLS) no broker. O HiveMQ CE roda com a extensão "Allow All", que aceita qualquer cliente. Isso serve para o desenvolvimento e para a apresentação, não para produção.

## 10. Por que essas escolhas (para a apresentação)

- **Desacoplamento (Eugster):** os apps conhecem apenas tópicos. O backend é mais um assinante, pode entrar ou sair sem que ninguém mude nada e se adapta ao formato que o publicador já usa.
- **QoS 1 (MQTT.pdf):** o material sugere QoS 0 para leituras frequentes em que perder uma mensagem não é crítico. Escolhemos QoS 1 porque o backend guarda histórico. O preço é a duplicação: depois do PUBACK, o broker esquece o packet ID e repassa um reenvio como mensagem nova (slide "QoS = 1 e falhas").
- **Modelo de falhas (Coulouris, cap. 2):** mensagem duplicada é falha arbitrária, e mensagem perdida é falha por omissão. O celular do motorista pode sofrer falha por parada (crash).
- **Princípio fim a fim (Saltzer):** o QoS 1 não evita duplicatas, e só a ponta final (o banco) consegue garantir que cada posição seja gravada uma vez. Por isso a deduplicação, a validação e a conversão do formato ficam no backend.
- **LWT e tempo limite (Coordenação e Acordo):** como no algoritmo valentão, a falha é detectada por tempo limite (`keepalive`). Um ônibus num trecho sem sinal pode ser marcado como offline sem ter falhado; a próxima posição corrige o estado.