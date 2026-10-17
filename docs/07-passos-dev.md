# Passos de Desenvolvimento — Tasks API

| Item | Valor |
|---|---|
| Base | [01-escopo-mvp.md](01-escopo-mvp.md) v1.3 · [02-backlog.md](02-backlog.md) v1.2 · [03-arquitetura-mvp.md](03-arquitetura-mvp.md) v1.2 |
| Versão do documento | 1.0 |
| Data | 2026-10-17 |
| Status | Rascunho |

## 1. Princípios

- **Fatias verticais.** Cada entrega atravessa todas as camadas (modelo → repositório → serviço → rota → teste). Não se constrói uma camada inteira antes de usá-la.
- **Testes junto com o código.** Nenhum commit de funcionalidade entra sem os testes dos critérios de aceite correspondentes do backlog. Para regras de negócio, o teste do serviço vem primeiro (sem HTTP, conforme RT02).
- **Commit atômico.** Cada commit tem um único propósito, compila, passa em todos os testes e deixa o CI verde. Um commit nunca depende de um commit posterior para funcionar.
- **Rastreabilidade.** Cada commit de funcionalidade cita o RF/RT ou a RN que implementa.
- **Documentos acompanham o código.** Mudança de decisão atualiza os documentos de `docs/` em commit `docs:` próprio, separado do código.
- **Código em inglês** (nomes, docstrings, comentários, logs e mensagens de erro da API); mensagens de commit em português, como no histórico atual.

### 1.1 Portão de qualidade de cada commit

Antes de cada commit, nesta ordem:

```bash
uv run ruff format .
uv run ruff check .
uv run mypy app
uv run pytest --cov=app --cov-fail-under=80
```

Os mesmos quatro comandos rodam no CI e bloqueiam o merge em caso de falha.

### 1.2 Padrão de commits (Conventional Commits)

Formato: `tipo(escopo): descrição no imperativo, em minúsculas, sem ponto final`.

| Tipo | Uso |
|---|---|
| `feat` | Nova funcionalidade da API (endpoint, regra de negócio). |
| `fix` | Correção de defeito. |
| `test` | Somente testes (ex.: teste de contrato adicional). |
| `refactor` | Mudança interna sem alterar comportamento. |
| `build` | Dependências e empacotamento (`pyproject.toml`, `requirements.txt`). |
| `ci` | Pipeline de CI. |
| `chore` | Configuração e tarefas de manutenção. |
| `docs` | Documentação, inclusive `docs/` e `README.md`. |
| `perf` | Melhoria de desempenho. |

Escopos sugeridos: `api`, `config`, `db`, `errors`, `health`, `task-groups`, `tasks`, `logging`, `openapi`, `deps`.

- Mudança que quebra o contrato da API usa `!` (ex.: `feat(tasks)!: ...`) e o rodapé `BREAKING CHANGE:`.
- Todo commit termina com o rodapé `Co-Authored-By` definido para a sessão.
- Um commit `feat` inclui, no mesmo commit, os testes da funcionalidade. Só vira `test` separado o teste que cobre comportamento já existente.

### 1.3 Fluxo de trabalho

1. Trabalhar em branch curta por etapa (`feat/task-groups-create`) ou direto na `main`, sempre com commits pequenos.
2. Rodar o portão de qualidade a cada commit.
3. Ao concluir uma etapa, marcar os critérios no `docs/02-backlog.md` (commit `docs:`).
4. Ao fechar uma release, criar uma tag: `v0.1.0` (R1), `v0.2.0` (R2) e `v1.0.0` (R3).

### 1.4 Estrutura de código alvo

```text
app/
  main.py              # application factory and router wiring
  config.py            # pydantic-settings
  db.py                # engine, session, PRAGMA foreign_keys=ON
  errors.py            # domain exceptions and RFC 9457 handlers
  models/              # SQLModel tables (task_group.py, task.py)
  schemas/             # Pydantic input/output (common.py, task_group.py, task.py)
  repositories/        # only layer that touches the database
  services/            # business rules (RN01–RN08), no web framework imports
  routes/              # thin FastAPI routers (health.py, task_groups.py, tasks.py)
tests/
  unit/                # services, no HTTP
  integration/         # endpoints via TestClient
  conftest.py          # isolated database per test, client and factories
```

---

## R1 — Core

### Etapa 1 — Esqueleto do projeto · RT01

1. **Objetivo:** projeto instalável em ambiente limpo com Python 3.14.
2. **Requisitos:** RT01.
3. **Testes:** `uv sync` em ambiente limpo; `uv run python --version` retorna `3.14.x`.
4. **Commits:**
   1. `build: inicializa projeto com uv e Python 3.14` (`.python-version`, `pyproject.toml`, `uv.lock`)
   2. `chore: cria estrutura de pacotes app e tests`
5. **Pronto quando:** os critérios de instalação do RT01 estão marcados.

### Etapa 2 — Configuração por ambiente · RT10

1. **Objetivo:** toda configuração vem de variáveis de ambiente.
2. **Requisitos:** RT10.
3. **Testes:** unitários de `Settings` (valor padrão, variável sobrescrevendo, valor inválido falha ao iniciar).
4. **Commits:**
   1. `feat(config): adiciona configuração via pydantic-settings`
   2. `chore(config): adiciona .env.example`
5. **Pronto quando:** `.env` está ignorado e `.env.example` versionado.

### Etapa 3 — Qualidade e CI · RT08, RT07

1. **Objetivo:** portão de qualidade automatizado desde o primeiro código.
2. **Requisitos:** RT08 (lint, formatação, tipos, CI em um sistema operacional), RT07 (cobertura mínima).
3. **Testes:** o próprio pipeline; um teste trivial garante que o `pytest` e a cobertura rodam.
4. **Commits:**
   1. `build: configura ruff, mypy e pytest no pyproject`
   2. `ci: adiciona pipeline de lint, tipos e testes com cobertura mínima de 80%`
5. **Pronto quando:** o CI fica verde na `main` e falha ao introduzir um erro de lint de propósito.

### Etapa 4 — Infraestrutura de testes · RT15

1. **Objetivo:** base de testes isolada, usada por todas as etapas seguintes.
2. **Requisitos:** RT15.
3. **Testes:** testes de sanidade das fixtures (banco novo a cada teste; ordem aleatória não altera o resultado).
4. **Commits:**
   1. `test: adiciona fixtures de banco isolado e cliente HTTP em conftest`
   2. `test: configura execução em ordem aleatória para detectar dependência entre testes`
5. **Pronto quando:** a suíte passa em qualquer ordem e em execução repetida.

### Etapa 5 — Aplicação mínima e health check · RF14, RT01

1. **Objetivo:** provar a pilha completa (uvicorn, FastAPI, sessão de banco) com a menor rota possível.
2. **Requisitos:** RF14, critério de arranque do RT01.
3. **Testes:** `GET /health` retorna `200` com banco ok; `503` com o banco indisponível; teste de fumaça sobe a aplicação.
4. **Commits:**
   1. `feat(db): adiciona engine, sessão e PRAGMA foreign_keys=ON em toda conexão` (com teste que prova o PRAGMA ativo)
   2. `feat(api): adiciona application factory do FastAPI`
   3. `feat(health): adiciona endpoint GET /health (RF14)`
   4. `docs: registra comando único para subir a API`
5. **Pronto quando:** `uv run uvicorn app.main:app` responde em `/health`.

### Etapa 6 — Tratamento de erros e paginação · RT14, RT05

1. **Objetivo:** contrato de erro e de listagem prontos antes dos endpoints de negócio.
2. **Requisitos:** RT14 (RFC 9457, `400` para query, `422` para corpo e caminho, `404`, `405`, `500` sem detalhes internos), RT05 (formato de dados), schema de listagem paginada.
3. **Testes:** um teste de contrato para cada código da tabela da seção 4.5 do escopo; `404` de rota inexistente e `405` em Problem Details; `500` sem stack trace.
4. **Commits:**
   1. `feat(errors): adiciona exceções de domínio e formato Problem Details`
   2. `feat(errors): mapeia erros de validação para 400 (query) e 422 (corpo e caminho)`
   3. `feat(errors): trata 404, 405 e 500 em application/problem+json`
   4. `feat(api): adiciona schema genérico de listagem paginada`
5. **Pronto quando:** todos os critérios do RT14 estão marcados.

### Etapa 7 — TaskGroup: persistência · RT03, RN01

1. **Objetivo:** modelo e repositório de grupos com as garantias do banco.
2. **Requisitos:** RT03 (modelo, `normalized_name` com índice único, `create_all`), RT02.
3. **Testes:** `Ação` e `AÇÃO` colidem; duas criações concorrentes do mesmo nome, uma falha por violação do índice; datetime UTC faz ida e volta.
4. **Commits:**
   1. `feat(task-groups): adiciona modelo TaskGroup com normalized_name único`
   2. `feat(task-groups): adiciona repositório de TaskGroup`
5. **Pronto quando:** os critérios do RT03 relativos a grupo estão marcados.

### Etapa 8 — TaskGroup: regras e endpoints · RF01–RF05

1. **Objetivo:** CRUD completo de grupos.
2. **Requisitos:** RF01 a RF05, RN01, RN03, RN08.
3. **Testes:** unitários do serviço (RN01, RN03) e de integração por endpoint, cobrindo todos os critérios de aceite do backlog.
4. **Commits:**
   1. `feat(task-groups): adiciona schemas de entrada e saída`
   2. `feat(task-groups): adiciona serviço com regras RN01 e RN03`
   3. `feat(task-groups): adiciona POST /task-groups (RF01)`
   4. `feat(task-groups): adiciona GET /task-groups com paginação e busca (RF02)`
   5. `feat(task-groups): adiciona GET /task-groups/{id} (RF03)`
   6. `feat(task-groups): adiciona PATCH /task-groups/{id} (RF04)`
   7. `feat(task-groups): adiciona DELETE /task-groups/{id} (RF05)`
5. **Pronto quando:** RF01 a RF05 estão com todos os critérios marcados.

### Etapa 9 — Task: persistência · RT03

1. **Objetivo:** modelo e repositório de tarefas com a chave estrangeira garantida.
2. **Requisitos:** RT03 (chave estrangeira obrigatória), RN02.
3. **Testes:** inserir tarefa com grupo inexistente é rejeitado pelo banco; excluir grupo com tarefas é bloqueado.
4. **Commits:**
   1. `feat(tasks): adiciona modelo Task com chave estrangeira para TaskGroup`
   2. `feat(tasks): adiciona repositório de Task`
5. **Pronto quando:** os critérios do RT03 relativos a tarefa estão marcados.

### Etapa 10 — Task: regras e endpoints · RF06, RF07, RF11–RF13

1. **Objetivo:** ciclo de vida completo da tarefa dentro de um grupo.
2. **Requisitos:** RF06, RF07 (por grupo), RF11, RF12, RF13; RN02 a RN08.
3. **Testes:** unitários do serviço (status padrão, `completed_at` preenchido e limpo, mover de grupo, campos gerados ignorados); integração por endpoint cobrindo os critérios do backlog.
4. **Commits:**
   1. `feat(tasks): adiciona schemas de entrada e saída`
   2. `feat(tasks): adiciona serviço com regras RN02 e RN04 a RN07`
   3. `feat(tasks): adiciona POST /task-groups/{group_id}/tasks (RF06)`
   4. `feat(tasks): adiciona GET /task-groups/{group_id}/tasks (RF07)`
   5. `feat(tasks): adiciona GET /tasks/{id} (RF11)`
   6. `feat(tasks): adiciona PATCH /tasks/{id} com transição de status e mudança de grupo (RF12)`
   7. `feat(tasks): adiciona DELETE /tasks/{id} (RF13)`
5. **Pronto quando:** RF06, RF07, RF11, RF12 e RF13 estão com todos os critérios marcados.

### Etapa 11 — Fechamento da R1

1. **Objetivo:** validar a release como um todo.
2. **Requisitos:** aceite da R1 no backlog.
3. **Testes:** teste de ponta a ponta do fluxo completo (criar grupo → criar tarefas → listar → concluir → excluir tarefas → excluir grupo); verificação de que nenhum endpoint cria tarefa sem grupo; cobertura de pelo menos 80%.
4. **Commits:**
   1. `test: adiciona teste de ponta a ponta do fluxo principal`
   2. `docs: marca critérios concluídos da R1 no backlog`
5. **Pronto quando:** todos os itens da R1 estão marcados e o CI está verde. Criar a tag `v0.1.0`.

---

## R2 — Piloto

### Etapa 12 — Contagem de tarefas por grupo · RF02 (parte 2)

1. **Requisitos:** `total_tasks` em `GET /task-groups`.
2. **Testes:** contagem correta; consulta única (sem N+1), verificada por contagem de instruções SQL.
3. **Commits:** `feat(task-groups): adiciona total_tasks à listagem de grupos`

### Etapa 13 — Listagem global e filtros · RF07 (parte 2), RF08

1. **Requisitos:** `GET /tasks`; filtros `status`, `priority`, `due_from`, `due_until` e `task_group_id`.
2. **Testes:** filtros isolados e combinados; intervalo invertido retorna `400`; `total` reflete o filtro.
3. **Commits:**
   1. `feat(tasks): adiciona GET /tasks com listagem de todos os grupos`
   2. `feat(tasks): adiciona filtros por status, prioridade, vencimento e grupo (RF08)`

### Etapa 14 — Busca e ordenação · RF09, RF10

1. **Requisitos:** parâmetro `q`; parâmetro `sort`.
2. **Testes:** busca sem diferenciar caixa; ordenação por `priority` (`low` < `medium` < `high`) e não alfabética; `due_date` nulo sempre por último; campo de ordenação inválido retorna `400`.
3. **Commits:**
   1. `feat(tasks): adiciona busca textual por q (RF09)`
   2. `feat(tasks): adiciona ordenação por sort (RF10)`

### Etapa 15 — Migrações com Alembic · RT03 (parte 2)

1. **Requisitos:** migração inicial igual ao esquema do `create_all`, modo *batch*, índices de consulta.
2. **Testes:** `upgrade head` e `downgrade base` em banco vazio; comparação do esquema migrado com o dos modelos.
3. **Commits:**
   1. `build(db): configura Alembic com modo batch para SQLite`
   2. `feat(db): adiciona migração inicial do esquema`
   3. `feat(db): adiciona índices de task_group_id, status e due_date`
   4. `refactor(db): remove create_all fora dos testes`

### Etapa 16 — Logs estruturados · RT09

1. **Requisitos:** log JSON por requisição; `X-Request-ID` propagado.
2. **Testes:** header recebido é reaproveitado; ausente, é gerado; presente em toda resposta; `500` loga stack trace.
3. **Commits:**
   1. `feat(logging): configura structlog com saída JSON`
   2. `feat(logging): adiciona middleware de X-Request-ID e log por requisição`

### Etapa 17 — Limite de corpo · RT11

1. **Requisitos:** `413` acima de 1 MB, com e sem `Content-Length`.
2. **Testes:** os dois casos, incluindo corpo em *chunks*.
3. **Commits:** `feat(api): adiciona limite de 1 MB no corpo com contagem durante a leitura`

### Etapa 18 — Contrato e documentação · RF15, RT04, RT13

1. **Requisitos:** `/docs` completo, OpenAPI versionado, README.
2. **Testes:** o arquivo OpenAPI versionado é igual ao gerado (falha no CI se divergir); todos os endpoints sob `/api/v1`.
3. **Commits:**
   1. `docs(openapi): descreve parâmetros, respostas e exemplos nos endpoints (RF15)`
   2. `feat(openapi): gera e versiona a especificação OpenAPI (RT04)`
   3. `ci: falha se a especificação OpenAPI versionada estiver desatualizada`
   4. `docs: adiciona README com instalação, execução e exemplos (RT13)`

### Etapa 19 — Medição preliminar de desempenho · RT06 (preliminar)

1. **Requisitos:** script de carga com 10 mil tarefas e p95 registrado.
2. **Testes:** o próprio script; resultado salvo no repositório.
3. **Commits:**
   1. `test(perf): adiciona script de carga com httpx2`
   2. `docs: registra medição preliminar de p95`

### Etapa 20 — Fechamento da R2

1. **Commits:** `docs: marca critérios concluídos da R2 no backlog`
2. **Pronto quando:** itens da R2 marcados, piloto executado e problemas registrados como novos itens de backlog. Criar a tag `v0.2.0`.

---

## R3 — Entrega final

### Etapa 21 — Desempenho · RT06

1. **Requisitos:** p95 abaixo de 200 ms em operações unitárias e em listagens de 100 itens.
2. **Testes:** o script da etapa 19, com as metas como critério de aprovação.
3. **Commits:**
   1. `perf(db): corrige desvios encontrados na medição de p95` (um commit por correção)
   2. `docs: registra resultado final de desempenho`

### Etapa 22 — Portabilidade · RT12

1. **Requisitos:** suíte passando em Windows e Linux.
2. **Testes:** matriz de CI com os dois sistemas.
3. **Commits:**
   1. `ci: executa a suíte em Windows e Linux`
   2. `fix: remove dependências de sistema operacional no código` (somente se necessário)

### Etapa 23 — Fechamento do MVP

1. **Requisitos:** aceite da R3 (critérios de sucesso do MVP).
2. **Testes:** instalação e subida a partir de ambiente limpo, seguindo apenas o README.
3. **Commits:** `docs: marca critérios concluídos da R3 e fecha o MVP`
4. **Pronto quando:** nenhum item fora de escopo foi implementado. Criar a tag `v1.0.0`.

---

## Resumo do mapeamento

| Etapa | Release | Requisitos |
|---|---|---|
| 1–5 | R1 | RT01, RT10, RT08, RT07, RT15, RF14 |
| 6 | R1 | RT14, RT05 |
| 7–8 | R1 | RT03, RF01–RF05 |
| 9–10 | R1 | RT03, RF06, RF07, RF11–RF13 |
| 11 | R1 | Aceite da R1 |
| 12–14 | R2 | RF02 (parte 2), RF07 (parte 2), RF08–RF10 |
| 15 | R2 | RT03 (parte 2) |
| 16–17 | R2 | RT09, RT11 |
| 18 | R2 | RF15, RT04, RT13 |
| 19–20 | R2 | RT06 (preliminar), aceite da R2 |
| 21–23 | R3 | RT06, RT12, aceite da R3 |
