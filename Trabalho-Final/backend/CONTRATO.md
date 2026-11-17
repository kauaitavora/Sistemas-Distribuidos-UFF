<!-- Trabalho-Final/backend/CONTRATO.md -->
# Contrato de mensagens MQTT — Cadê o BusUFF?

> **Status: PROPOSTA (v0.2)**, ajustada com as respostas do João (16/11). Itens marcados com **[A VALIDAR]** dependem de decisão do grupo.

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

Regras para `rota_id` e `veiculo_id`:
- apenas letras minúsculas sem acento, números e hífen (ex.: `rota-1`, `onibus-03`), com até 32 caracteres;
- nunca usar `/`, `+`, `#` ou espaço, que são caracteres especiais do MQTT;
- os valores válidos vêm da API do backend (seção 6).

O tópico de status fica **fora** de `rotas/` de propósito: quem assina `rotas/#` recebe só posições.

## 3. Mensagem de posição

Publicada em `rotas/<rota_id>/<veiculo_id>`, em JSON (UTF-8), a cada 1 a 5 segundos enquanto a viagem estiver ativa (hoje o app usa 1 s).

```json
{
  "veiculo_id": "onibus-01",
  "rota_id": "rota-1",
  "horario_id": 3,
  "timestamp": "2026-11-20T10:30:05.123Z",
  "lat": -22.505253,
  "lng": -41.920643,
  "precisao_m": 12.5,
  "velocidade_ms": 8.3,
  "direcao_graus": 90.0
}
```

| Campo | Tipo | Obrigatório | Significado |
|---|---|---|---|
| `veiculo_id` | texto | sim | ônibus que está enviando; deve ser igual ao do tópico |
| `rota_id` | texto | sim | rota escolhida pelo motorista; deve ser igual à do tópico |
| `horario_id` | inteiro ou `null` | não | horário escolhido pelo motorista (id vindo da API); pode ser omitido |
| `timestamp` | texto ISO 8601 em UTC (terminado em `Z`) | sim | momento da leitura do GPS |
| `lat` / `lng` | número (graus decimais) | sim | latitude (−90 a 90) e longitude (−180 a 180) |
| `precisao_m` | número ou `null` | não | margem de erro, em metros |
| `velocidade_ms` | número ou `null` | não | velocidade, em **m/s** |
| `direcao_graus` | número ou `null` | não | direção de 0 a 360, a partir do norte |

De onde vem cada campo no app (objeto `Position` do Capacitor):
- `timestamp` ← `new Date(position.timestamp).toISOString()`
- `lat` ← `coords.latitude` e `lng` ← `coords.longitude`
- `precisao_m` ← `coords.accuracy`, `velocidade_ms` ← `coords.speed` e `direcao_graus` ← `coords.heading`

## 4. Mensagem de status (online/offline e LWT)

Publicada em `status/<veiculo_id>`, com QoS 1 e **retain = true**, para que quem se conectar depois saiba o estado atual.

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

- **Inválida** (JSON quebrado, campo obrigatório ausente, tipo ou faixa errados, tópico diferente do payload, rota, horário ou veículo inexistente): é descartada e registrada em log, sem derrubar o assinante.
- **Duplicada**: com QoS 1, a mesma mensagem pode chegar mais de uma vez. O backend considera duplicada a posição com o mesmo `veiculo_id` e o mesmo `timestamp`, e grava apenas uma.
- **Status**: `offline` marca o ônibus como fora de serviço; uma nova posição ou um `online` o reativa.

## 6. API REST do backend (prévia; detalhes na Etapa 4)

Porta **8080**. Rotas previstas:
- `GET /rotas`: rotas disponíveis
- `GET /rotas/{rota_id}/horarios`: horários de uma rota
- `GET /veiculos`: ônibus cadastrados
- `GET /rotas/{rota_id}/posicoes/ultima`: última posição de cada ônibus da rota (até 10 minutos atrás)

## 7. Itens [A VALIDAR] pelo grupo

1. **Origem do `veiculo_id`** [A VALIDAR]: (A) o app gera um id fixo por celular, ou (B) o motorista escolhe o ônibus numa lista vinda de `GET /veiculos`, como faz com as rotas. Proposta do backend: **B**.
2. **Formato do `timestamp`** [A VALIDAR]: proposta de ISO 8601 em UTC. Alternativa: número em milissegundos.
3. **Intervalo de envio** [A VALIDAR]: manter 1 s ou passar para 2 a 5 s.

Decidido em 16/11 (respostas do João):
- as rotas são pré-fixadas, e o motorista escolhe uma da lista;
- o horário é opcional, com dados de exemplo enquanto não houver horários oficiais;
- tudo roda nas máquinas do grupo por enquanto;
- o broker é o HiveMQ CE (o Mosquitto serve para testes locais).

## 8. Mudanças necessárias nos apps (resumo)

- **João**: publicar em `rotas/<rota_id>/<veiculo_id>` com QoS 1 e o payload da seção 3; configurar o LWT e o `keepalive` (seção 4); tornar o endereço do broker configurável.
- **Kauai**: ler `lat` e `lng` em vez de `coords.latitude` e `coords.longitude`; usar um marcador por `veiculo_id`; criar a tela de escolha de rota (e de ônibus, na opção B; o horário é opcional) consumindo a API.

## 9. Fora do escopo

Autenticação e criptografia (TLS) no broker. O HiveMQ CE roda com a extensão "Allow All", que aceita qualquer cliente. Isso serve para o desenvolvimento e para a apresentação, não para produção.

## 10. Por que essas escolhas (para a apresentação)

- **Desacoplamento (Eugster):** os apps conhecem apenas tópicos. O backend é mais um assinante e pode entrar ou sair sem que ninguém mude nada.
- **QoS 1 (MQTT.pdf):** o material sugere QoS 0 para leituras frequentes em que perder uma mensagem não é crítico. Escolhemos QoS 1 porque o backend guarda histórico. O preço é a duplicação: depois do PUBACK, o broker esquece o packet ID e repassa um reenvio como mensagem nova (slide "QoS = 1 e falhas").
- **Modelo de falhas (Coulouris, cap. 2):** mensagem duplicada é falha arbitrária, e mensagem perdida é falha por omissão. O celular do motorista pode sofrer falha por parada (crash).
- **Princípio fim a fim (Saltzer):** o QoS 1 não evita duplicatas, e só a ponta final (o banco) consegue garantir que cada posição seja gravada uma vez. Por isso a deduplicação e a validação, incluindo conferir se tópico e payload batem, ficam no backend.
- **LWT e tempo limite (Coordenação e Acordo):** como no algoritmo valentão, a falha é detectada por tempo limite (`keepalive`). Um ônibus num trecho sem sinal pode ser marcado como offline sem ter falhado; a próxima posição corrige o estado.