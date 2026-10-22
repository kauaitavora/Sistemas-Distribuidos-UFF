# Tratamento Global de Erros (AppError)

## Por que centralizar o Tratamento de Erros?

1. O Problema da Abordagem Manual

Sem um middleware global:

- Todos os métodos do Controller precisam de um bloco try/catch.
- Erros não previstos (falha em runtime, sintaxe ou nulo) estouram sem tratamento, podendo expor dados sensíveis do servidor (stack trace).
- A resposta de erro não tem um padrão único na API.

2. A Solução: AppError + Global Error Middleware

- AppError (Camada de Domínio): Uma classe customizada para erros operacionais/esperados (ex: e-mail já cadastrado, recurso não encontrado). Ela guarda a mensagem e o statusCode HTTP apropriado (400, 404, 409).
- Middleware Global (Camada de Infraestrutura): Captura qualquer erro lançado (throw) na aplicação. Se for um AppError, responde com a mensagem e o código definidos. Se for um erro desconhecido, loga a falha e responde um seguro 500 Internal Server Error.

## Todo o Código Necessário

Passo 1: A Classe de Erro de Domínio (src/domain/errors/app-error.ts)

Esta classe não depende de nenhum framework.

[Código da Classe AppError](src/domain/errors/app.error.ts)

Passo 2: Lançando Erros nos Casos de Uso

Atualize os Casos de Uso para lançar o AppError quando uma regra de negócio for violada.

[Create User](src/application/useCases/createUser.ts)

Passo 3: Limpando o Controller (src/infrastructure/http/controllers/user.controller.ts)

Sem os blocos try/catch repetitivos. As exceções passam direto para o middleware global:

[User Controller](src/infrastructure/http/controllers/user.controller.ts)

Passo 4: O Middleware Global (src/infrastructure/http/middlewares/error-handler.ts)

No Express, um middleware de erro precisa obrigatoriamente receber 4 parâmetros: (error, req, res, next).

[Error Handler Middleware](src/infrastructure/http/middlewares/errorHandler.ts)

Passo 5: Registrando no server.ts (src/main/server.ts)

⚠️ Atenção: O errorHandler DEVE ser registrado DEPOIS de todas as rotas e do Swagger!

[Server Registration Example](src/main/server.ts)

## Modelo do README

[Exemplo do Readme](docs/EXEMPLO.md)
