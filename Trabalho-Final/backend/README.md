<!-- Trabalho-Final/backend/README.md -->
# Backend — Cadê o BusUFF?

Backend do Trabalho Final de Sistemas Distribuídos (UFF, 2026.2). Recebe as posições dos ônibus pelo MQTT, guarda no PostgreSQL e as oferece por uma API REST.

```text
App do motorista ──MQTT──► broker ──MQTT──► app dos alunos (mapa)
                             │
                             └──TCP 1883──► assinante ──► PostgreSQL ◄── API REST (porta 8080)
```

São dois processos independentes, que só se comunicam pelo banco:

- **Assinante MQTT** (`app/mqtt/assinante.py`): assina `rotas/+/+` e `status/+`, valida as mensagens, descarta as inválidas e as duplicadas e grava no banco. Pode rodar em várias réplicas, com eleição de líder (só a líder grava).
- **API REST** (`app/main.py`): só lê o banco.

O formato das mensagens (tópicos, conteúdo, QoS e LWT) está no [CONTRATO.md](CONTRATO.md).

## Pré-requisitos

| Programa | Versão testada | Observação |
|---|---|---|
| Python | 3.12 | precisa ser **3.10 ou maior** |
| PostgreSQL | 17 | |
| Broker MQTT | HiveMQ CE 2026.5 | qualquer broker com TCP na porta 1883 (ex.: Mosquitto) |

Testado no Windows 10. Os comandos de macOS seguem o mesmo roteiro.

## 1. Banco de dados (uma vez só)

Crie um usuário e um banco só para o projeto. Escolha uma senha (só letras e números) e anote: ela vai no `.env`.

**Windows (PowerShell):**

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres
```

**macOS (Homebrew):**

```bash
brew install postgresql@17
brew services start postgresql@17
export PATH="$(brew --prefix postgresql@17)/bin:$PATH"
psql postgres
```

Dentro do `psql`, nos dois sistemas (um comando por vez):

```sql
CREATE ROLE busuff WITH LOGIN;
\password busuff
CREATE DATABASE busuff OWNER busuff;
\q
```

**macOS com Docker (alternativa à seção acima):** se o Docker Desktop já estiver instalado, este comando cria o banco pronto (troque a senha). Se outro PostgreSQL já estiver usando a porta 5432, pare-o antes.

```bash
docker run -d --name busuff-db -p 5432:5432 -e POSTGRES_USER=busuff -e POSTGRES_PASSWORD=troque-esta-senha -e POSTGRES_DB=busuff postgres:17
```

## 2. Ambiente Python (uma vez só)

Dentro da pasta `Trabalho-Final/backend`:

**Windows (PowerShell):**

```powershell
python --version                 # precisa ser 3.10 ou maior
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS (Terminal):**

```bash
python3 --version                # precisa ser 3.10 ou maior (o python3 que vem no macOS é 3.9 e não serve)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Se o `python3` for 3.9: rode `brew install python@3.12` e crie o ambiente com `python3.12 -m venv .venv`.

Abra o `.env` e troque `troque-esta-senha` pela senha do passo 1. O `.env` não vai para o Git; só o `.env.example` é versionado.

Em todo terminal novo, ative o ambiente antes dos comandos: `.\.venv\Scripts\Activate.ps1` (Windows) ou `source .venv/bin/activate` (macOS).

## 3. Tabelas e dados de exemplo

```bash
python -m app.core.database   # deve mostrar "Conexão OK: usuário=busuff, banco=busuff"
python -m app.seed            # cria as tabelas e insere os dados de exemplo
```

O seed pode ser rodado de novo sem duplicar nada. Dados de exemplo:

- rotas `rota-1`, `rota-2` e `rota-3`, com saídas às 07:00, 12:00 e 17:30;
- ônibus `onibus-01`, `onibus-02` e `onibus-03`.

## 4. Executar

Cada processo num terminal próprio, com o ambiente ativo:

| # | Processo | Comando |
|---|---|---|
| 1 | Broker | HiveMQ: `bin\run.bat` (Windows) ou `./bin/run.sh` (macOS), na pasta do HiveMQ. Mosquitto: `mosquitto -c ../busuff-mosquitto.conf` |
| 2 | Assinante | `python -m app.mqtt.assinante` |
| 3 | API | `uvicorn app.main:app --port 8080` |

- Documentação interativa da API: http://localhost:8080/docs
- Para outro aparelho (ex.: celular) acessar a API: `uvicorn app.main:app --host 0.0.0.0 --port 8080` e use o IP do computador. No Windows, o Wi-Fi precisa estar como rede **Privada**.
- Porta 8080 ocupada: use outra, como `--port 8081`, e avise quem consome a API.

Endereços da API:

| Endereço | Retorna |
|---|---|
| `GET /rotas` | rotas |
| `GET /rotas/{rota_id}/horarios` | horários da rota |
| `GET /rotas/{rota_id}/posicoes/ultima?minutos=10` | última posição de cada ônibus da rota |
| `GET /veiculos` | ônibus e estado online/offline |
| `GET /veiculos/{veiculo_id}/posicoes?limite=50` | histórico de um ônibus |

## 5. Roteiro de demonstração

Com broker, assinante e API rodando, use um 4º terminal (com o ambiente ativo):

| Demonstração | Comando | O que observar |
|---|---|---|
| Fluxo normal | `python -m app.mqtt.simulador` | no assinante: `online`, 5 `[GRAVADA]` e `offline`; a posição aparece em `/rotas/rota-1/posicoes/ultima` |
| Validação e duplicatas (QoS 1) | `python -m app.mqtt.casos_de_teste` | cada caso mostra o resultado esperado; `[DUPLICADA]` nos casos 10 e 17 |
| Queda do celular (LWT) | `python -m app.mqtt.simulador --rota rota-3 --veiculo onibus-03 --sem-sinal` | `offline` cerca de 22 s depois de "Simulando perda de sinal" |
| Assinante fora do ar | pare o assinante, rode o simulador e ligue o assinante de novo | as 5 posições chegam de uma vez (sessão persistente) |
| Eleição de líder | pare o assinante; em 3 terminais, `python -m app.mqtt.assinante --replica 1` (depois 2 e 3); rode `python -m app.mqtt.simulador --rota rota-2 --veiculo onibus-02 --quantidade 40` e feche o terminal da réplica 3 | a réplica 2 assume em cerca de 2 s, sem perder posições |

Para conferir que nenhuma posição foi gravada duas vezes, rode no `psql` (precisa voltar 0 linhas):

```sql
SELECT veiculo_id, timestamp, count(*) FROM posicao GROUP BY veiculo_id, timestamp HAVING count(*) > 1;
```

## 6. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `TypeError: unsupported operand type(s) for \|` ao iniciar | Python menor que 3.10 |
| `Não foi possível conectar em localhost:1883` | broker desligado |
| `UnicodeDecodeError` ao conectar no banco (Windows) | usuário ou senha errados no `.env` |
| `address already in use` ao subir a API | porta ocupada; use outra com `--port` |
| `[DESCARTADA] ... rota inexistente` para mensagens do app | o app usa um id de rota que não está no banco (veja `GET /rotas`) |
| Muitas linhas `[DUPLICADA]` ao ligar o assinante | normal: o broker reentrega o que guardou na sessão e as posições retidas |

## Estrutura

```text
app/
├── core/database.py        conexão com o PostgreSQL
├── models.py               tabelas (rota, horario, veiculo, posicao)
├── schemas.py              formato das respostas da API
├── init_db.py              cria as tabelas
├── seed.py                 dados de exemplo
├── main.py                 API REST (FastAPI)
├── api/                    endereços da API (rotas e veículos)
└── mqtt/
    ├── assinante.py        assinante MQTT (modo único ou réplica)
    ├── validacao.py        regras do contrato
    ├── gravacao.py         gravação idempotente no banco
    ├── eleicao.py          eleição de líder (algoritmo do valentão)
    ├── simulador.py        simula o app do motorista
    └── casos_de_teste.py   mensagens válidas e inválidas para teste
```