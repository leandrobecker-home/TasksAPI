# Backlog do MVP — Tasks API

| Item | Valor |
|---|---|
| Base | [01-escopo-mvp.md](01-escopo-mvp.md) v1.3 |
| Versão do documento | 1.3 |
| Data | 2026-10-17 |
| Status | Rascunho |

## Convenções

- **RF**: requisito funcional. Os IDs são os mesmos do documento de escopo (seção 4).
- **RT**: requisito técnico. Cada RT corresponde ao RNF de mesmo número no escopo (seção 5); por exemplo, RT04 implementa o RNF04.
- **RN**: regra de negócio do escopo (seção 3.4), citada nos critérios que a validam.
- Caminhos de endpoint são relativos a `/api/v1`, exceto `/health` e `/docs`.
- Um item "(parte 2)" completa, em release posterior, um item iniciado antes. Ele só é considerado concluído quando as duas partes estiverem prontas.
- Um item só é marcado como concluído quando **todos** os seus critérios de aceite estão marcados.

## Definição de pronto (vale para todo item)

- [ ] Critérios de aceite cobertos por testes automatizados (`pytest`) que passam.
- [ ] Testes seguem a estratégia do RT15 (banco isolado por teste, sem dependência de ordem).
- [ ] `ruff check`, `ruff format --check` e `mypy` sem erros.
- [ ] Cobertura total de pelo menos 80% (RT07).
- [ ] Respostas de erro no formato RFC 9457, com os códigos da seção 4.5 do escopo (RT14).
- [ ] Alterações apresentadas e aprovadas pelo usuário antes do commit (docs/07, seção 1.4).

## Visão geral das releases

| Release | Objetivo | RF | RT |
|---|---|---|---|
| R1 — Core | CRUD de grupos e tarefas funcionando de ponta a ponta, com listagem por grupo e testes desde o início. | RF01–RF07, RF11–RF14 | RT01, RT02, RT03, RT05, RT07, RT08, RT10, RT14, RT15 |
| R2 — Piloto | API utilizável por clientes do piloto: consulta avançada, listagem global, migrações, documentação e operação. | RF02 (parte 2), RF07 (parte 2), RF08, RF09, RF10, RF15 | RT03 (parte 2), RT04, RT06 (preliminar), RT09, RT11, RT13 |
| R3 — Entrega final | Metas de desempenho e portabilidade atingidas. | — | RT06, RT12 |

### Decisões de corte do escopo da R1

- `PUT /tasks/{id}` saiu do MVP (fora de escopo); o `PATCH` cobre todas as edições.
- `total_tasks` na listagem de grupos foi para a R2.
- A listagem global `GET /tasks` foi para a R2; a R1 lista tarefas apenas por grupo.
- O esquema do banco é criado com `create_all` na R1; as migrações com Alembic entram na R2. Até lá, alterar o modelo exige recriar o banco local.
- Não será usado nenhum pipeline de CI: o portão de qualidade roda localmente antes de cada commit.

---

## R1 — Core

### Fundação técnica

- [ ] **RT01 — Plataforma Python 3.14 com `uv`**
  - [x] `.python-version` contém `3.14` e está versionado.
  - [x] `pyproject.toml` e `uv.lock` versionados; `uv sync` instala tudo a partir de um ambiente limpo.
  - [x] `uv run python --version` retorna `Python 3.14.x`.
  - [ ] Um único comando documentado sobe a API localmente.
  - [ ] Teste de fumaça (*smoke test*) sobe a aplicação e responde `200` em `GET /health`.

- [ ] **RT02 — Arquitetura em camadas**
  - [ ] Código separado em rotas, serviços e repositórios.
  - [ ] Serviços não importam nada do framework web (verificado em revisão ou por regra de import).
  - [ ] Regras de negócio (RN01–RN08) implementadas na camada de serviço e testadas sem subir o servidor HTTP.

- [ ] **RT03 — Persistência com ORM (esquema por `create_all` na R1)**
  - [ ] Tabelas `task_groups` e `tasks` criadas por `SQLModel.metadata.create_all`.
  - [ ] `tasks.task_group_id` é chave estrangeira obrigatória para `task_groups.id`.
  - [ ] `PRAGMA foreign_keys=ON` executado em toda conexão; teste prova que inserir tarefa com grupo inexistente é rejeitado pelo banco.
  - [ ] Coluna interna `normalized_name` (`strip` + `casefold`) com índice único; teste prova que `Ação` e `AÇÃO` colidem.
  - [ ] Duas criações concorrentes do mesmo nome: uma retorna `201` e a outra `409` (a unicidade é garantida pelo banco, não só por consulta prévia).
  - [ ] Datetimes gravados em UTC e lidos com fuso UTC; teste de ida e volta.
  - [ ] Banco SQLite configurado por variável de ambiente; nenhuma consulta SQL fora da camada de repositório.

- [ ] **RT05 — Formato de dados**
  - [ ] Requisições e respostas em JSON UTF-8 (`Content-Type: application/json`).
  - [ ] Datas no formato `YYYY-MM-DD`; datetimes em ISO 8601 com fuso UTC (`Z` ou `+00:00`).
  - [ ] Data em formato inválido retorna `422`.

- [ ] **RT07 — Cobertura de testes**
  - [ ] Testes unitários dos serviços e testes de integração dos endpoints.
  - [ ] Cada regra RN01–RN08 tem ao menos um teste dedicado, criado junto com a funcionalidade.
  - [x] `pytest --cov=app --cov-fail-under=80` configurado e executado localmente antes de cada commit desde a R1.

- [x] **RT08 — Lint, formatação e tipos**
  - [x] Configuração de `ruff` e `mypy` no `pyproject.toml`.
  - [x] `uv run ruff check .`, `uv run ruff format --check .` e `uv run mypy app` passam sem erros.
  - [x] Os quatro comandos do portão de qualidade (docs/07, seção 1.1) passam antes de cada commit.

- [x] **RT10 — Configuração por ambiente**
  - [x] Toda configuração (URL do banco, nível de log, porta) lida de variáveis de ambiente.
  - [x] `.env.example` versionado com todas as variáveis e valores de exemplo.
  - [x] `.env` no `.gitignore`; nenhum segredo no repositório.

- [ ] **RT14 — Tratamento de erros (RFC 9457)**
  - [ ] Toda resposta de erro usa `application/problem+json` com `type`, `title`, `status`, `detail` e `instance`.
  - [ ] Parâmetro de query inválido retorna `400`; corpo inválido e `id` de caminho que não é UUID retornam `422`.
  - [ ] Rota inexistente retorna `404` e método não permitido retorna `405`, ambos em Problem Details.
  - [ ] Corpo com JSON malformado retorna `400`.
  - [ ] Erro `500` não expõe stack trace, SQL ou caminhos internos.
  - [ ] Cada código da tabela da seção 4.5 do escopo tem teste de contrato dedicado.

- [ ] **RT15 — Estratégia de testes**
  - [ ] `pytest` configurado no `pyproject.toml` (diretório `tests/`, separação `unit` e `integration`).
  - [ ] Cada teste usa banco SQLite próprio (em memória ou arquivo temporário), criado e descartado por fixture.
  - [ ] Os testes passam em qualquer ordem e em execução repetida.
  - [ ] Fixtures de cliente HTTP (`TestClient` com `httpx2`) e fábricas de `TaskGroup` e `Task` compartilhadas.

### TaskGroups

- [ ] **RF01 — Criar grupo** · `POST /task-groups`
  - [ ] Com `name` válido, retorna `201`, o grupo criado e o header `Location: /api/v1/task-groups/{id}`.
  - [ ] `id`, `created_at` e `updated_at` são gerados pelo servidor; valores enviados pelo cliente são ignorados (RN08).
  - [ ] Campo desconhecido no corpo retorna `422` (RN08).
  - [ ] Espaços nas pontas de `name` são removidos antes de salvar.
  - [ ] `name` ausente, vazio ou com mais de 100 caracteres retorna `422`.
  - [ ] `description` com mais de 500 caracteres retorna `422`.
  - [ ] `name` já existente, inclusive com outra combinação de maiúsculas/minúsculas ou acentos, retorna `409` (RN01).

- [ ] **RF02 — Listar grupos** · `GET /task-groups`
  - [ ] Retorna `200` no formato de listagem (`items`, `page`, `page_size`, `total`).
  - [ ] Paginação com padrão `page_size = 20` e máximo `100`; valor acima do máximo ou não positivo retorna `400`.
  - [ ] Parâmetro `q` filtra por `name`, sem diferenciar maiúsculas/minúsculas.
  - [ ] Sem grupos cadastrados, retorna `items: []` e `total: 0`.

- [ ] **RF03 — Consultar grupo** · `GET /task-groups/{id}`
  - [ ] Grupo existente retorna `200` com todos os campos.
  - [ ] `id` inexistente retorna `404`.
  - [ ] `id` que não é UUID válido retorna `422`.

- [ ] **RF04 — Atualizar grupo** · `PATCH /task-groups/{id}`
  - [ ] Altera apenas os campos enviados (`name`, `description`) e retorna `200` com o grupo atualizado.
  - [ ] `updated_at` muda; `created_at` permanece igual.
  - [ ] Novo `name` igual ao de outro grupo retorna `409` (RN01); manter o próprio nome não é conflito.
  - [ ] Mesmas validações de tamanho do RF01.
  - [ ] Grupo inexistente retorna `404`.

- [ ] **RF05 — Excluir grupo** · `DELETE /task-groups/{id}`
  - [ ] Grupo sem tarefas retorna `204` e deixa de ser encontrado (`GET` retorna `404`).
  - [ ] Grupo com ao menos uma tarefa retorna `409` e não é excluído (RN03).
  - [ ] Grupo inexistente retorna `404`.

### Tasks

- [ ] **RF06 — Criar tarefa no grupo** · `POST /task-groups/{group_id}/tasks`
  - [ ] Com `title` válido, retorna `201`, a tarefa criada e o header `Location: /api/v1/tasks/{id}`.
  - [ ] A tarefa criada tem `task_group_id` igual ao `group_id` do caminho.
  - [ ] `group_id` inexistente retorna `404`, e nenhuma tarefa é criada (RN02).
  - [ ] Sem `status` e `priority`, a tarefa nasce com `pending` e `medium` (RN05).
  - [ ] `title` ausente, vazio (após remover espaços) ou com mais de 200 caracteres retorna `422`.
  - [ ] `description` com mais de 2000 caracteres retorna `422`.
  - [ ] `status` ou `priority` fora dos valores permitidos retorna `422`.
  - [ ] Campos gerados (`id`, `created_at`, `updated_at`, `completed_at`) enviados pelo cliente são ignorados; qualquer outro campo desconhecido retorna `422` (RN08).
  - [ ] Criada já com `status = completed`, a tarefa tem `completed_at` preenchido (RN07).

- [ ] **RF07 — Listar tarefas de um grupo** · `GET /task-groups/{group_id}/tasks`
  - [ ] Retorna `200` no formato de listagem, com paginação igual à do RF02.
  - [ ] Retorna apenas as tarefas daquele grupo.
  - [ ] `group_id` inexistente retorna `404`.
  - [ ] Ordem padrão: `created_at` decrescente.

- [ ] **RF11 — Consultar tarefa** · `GET /tasks/{id}`
  - [ ] Tarefa existente retorna `200` com todos os campos, incluindo `task_group_id`.
  - [ ] `id` inexistente retorna `404`; `id` que não é UUID válido retorna `422`.

- [ ] **RF12 — Atualizar tarefa parcialmente** · `PATCH /tasks/{id}`
  - [ ] Altera apenas os campos enviados e retorna `200`; `updated_at` muda.
  - [ ] Qualquer transição entre `pending`, `in_progress` e `completed` é aceita (RN06).
  - [ ] Mudar para `completed` preenche `completed_at`; sair de `completed` limpa o campo (RN07).
  - [ ] `completed_at` enviado pelo cliente é ignorado (RN08).
  - [ ] Alterar `task_group_id` para um grupo existente move a tarefa; para um grupo inexistente, retorna `422` (RN04).
  - [ ] Mesmas validações de campo do RF06.
  - [ ] Tarefa inexistente retorna `404`.

- [ ] **RF13 — Excluir tarefa** · `DELETE /tasks/{id}`
  - [ ] Tarefa existente retorna `204` e é removida fisicamente (`GET` retorna `404`).
  - [ ] Após excluir a última tarefa de um grupo, o grupo pode ser excluído (RF05).
  - [ ] Tarefa inexistente retorna `404`.

### Operação

- [ ] **RF14 — Health check** · `GET /health`
  - [ ] Retorna `200` com `{"status": "ok", "database": "ok"}` quando a aplicação e o banco respondem.
  - [ ] Com o banco indisponível, retorna `503` com `"database": "error"`.
  - [ ] Não exige o prefixo `/api/v1`.

### Aceite da release R1

- [ ] Todos os itens da R1 concluídos.
- [ ] Fluxo de ponta a ponta validado: criar grupo → criar tarefas → listar por grupo → concluir uma tarefa → excluir tarefas → excluir grupo.
- [ ] Não é possível criar uma tarefa sem um grupo existente, por nenhum endpoint.
- [ ] Cobertura de testes de pelo menos 80% e portão de qualidade sem erros.

---

## R2 — Piloto

### Consulta avançada

- [ ] **RF02 (parte 2) — Contagem de tarefas por grupo** · `GET /task-groups`
  - [ ] Cada item traz `total_tasks` com a quantidade correta de tarefas do grupo.
  - [ ] A contagem é obtida em uma única consulta (sem uma consulta por grupo).

- [ ] **RF07 (parte 2) — Listagem global de tarefas** · `GET /tasks`
  - [ ] Retorna tarefas de todos os grupos, no formato de listagem e com a mesma paginação do RF02.
  - [ ] Ordem padrão: `created_at` decrescente.

- [ ] **RF08 — Filtros da listagem de tarefas** · `GET /task-groups/{group_id}/tasks`, `GET /tasks`
  - [ ] `status` e `priority` filtram pelo valor exato; valor inválido retorna `400`.
  - [ ] `due_from` e `due_until` filtram por intervalo fechado de `due_date`.
  - [ ] `due_from` posterior a `due_until` retorna `400`.
  - [ ] Em `GET /tasks`, `task_group_id` filtra pelo grupo.
  - [ ] Filtros combinados se somam (operador E) e `total` reflete o resultado filtrado.

- [ ] **RF09 — Busca textual** · `GET /task-groups/{group_id}/tasks`, `GET /tasks`
  - [ ] `q` encontra tarefas com o termo em `title` ou `description`, sem diferenciar maiúsculas/minúsculas.
  - [ ] `q` combina com filtros e paginação.
  - [ ] `q` vazio é tratado como ausente.

- [ ] **RF10 — Ordenação** · `GET /task-groups/{group_id}/tasks`, `GET /tasks`
  - [ ] `sort` aceita `created_at`, `due_date` e `priority`, com `-` para ordem decrescente.
  - [ ] Ordenação por `priority` segue a ordem `low` < `medium` < `high`, e não a ordem alfabética.
  - [ ] Campo de ordenação inválido retorna `400`.
  - [ ] Tarefas sem `due_date` aparecem por último em qualquer direção.

### Persistência

- [ ] **RT03 (parte 2) — Migrações versionadas com Alembic**
  - [ ] Migração inicial reproduz exatamente o esquema criado por `create_all` na R1.
  - [ ] Alembic configurado em modo *batch* para `ALTER TABLE` no SQLite.
  - [ ] Migrações aplicam e revertem sem erro em banco vazio; teste automatizado executa `upgrade head` e `downgrade base`.
  - [ ] Índices de consulta (`task_group_id`, `status`, `due_date`) criados por migração.
  - [ ] `create_all` deixa de ser usado fora dos testes.

### Contrato e documentação

- [ ] **RF15 — Documentação interativa** · `GET /docs`
  - [ ] `/docs` exibe todos os endpoints de grupos, tarefas e operação.
  - [ ] Cada endpoint documenta parâmetros, corpo, respostas de sucesso e de erro, com exemplos.
  - [ ] É possível executar requisições pela página.

- [ ] **RT04 — Contrato OpenAPI versionado**
  - [ ] Especificação OpenAPI 3.x gerada a partir do código, sem edição manual.
  - [ ] Arquivo da especificação versionado no repositório.
  - [ ] Teste automatizado falha se o arquivo versionado estiver diferente do gerado pelo código.
  - [ ] Todos os endpoints de negócio respondem sob `/api/v1`.

- [ ] **RT13 — README**
  - [ ] Instruções de instalação, configuração (`.env`), execução, migrações e testes.
  - [ ] Exemplos de requisição para o fluxo principal (criar grupo, criar tarefa, listar, concluir).
  - [ ] Seguindo apenas o README, uma pessoa nova sobe a API em ambiente limpo.

### Operação e segurança

- [ ] **RT09 — Logs estruturados**
  - [ ] Cada requisição gera um log JSON com nível, timestamp, método, rota, status HTTP, duração e `request_id`.
  - [ ] Header `X-Request-ID` recebido é reaproveitado; se ausente, um novo é gerado.
  - [ ] Toda resposta devolve o `X-Request-ID`.
  - [ ] Erros `500` são logados com stack trace.

- [ ] **RT11 — Limite e validação de entrada**
  - [ ] Corpo maior que 1 MB retorna `413` quando o cliente envia `Content-Length`.
  - [ ] Corpo maior que 1 MB retorna `413` também **sem** `Content-Length` (transferência em *chunks*), contando os bytes durante a leitura.
  - [ ] Teste automatizado cobre os dois casos acima.

### Desempenho (verificação antecipada)

- [ ] **RT06 (preliminar) — Medição inicial de p95**
  - [ ] Script de carga versionado popula 10 mil tarefas e mede o p95 das operações unitárias e da listagem de 100 itens.
  - [ ] Resultado registrado no repositório; a R3 só refina e fecha a meta.

### Aceite da release R2

- [ ] Todos os itens da R2 concluídos.
- [ ] Clientes do piloto conseguem integrar usando apenas o `/docs` e o README.
- [ ] Problemas encontrados no piloto registrados como itens novos de backlog.

---

## R3 — Entrega final

- [ ] **RT06 — Desempenho**
  - [ ] Script de carga reproduzível versionado, com base de 10 mil tarefas distribuídas em grupos.
  - [ ] p95 abaixo de 200 ms em operações unitárias (`GET`, `POST`, `PATCH`, `DELETE` de grupo e tarefa).
  - [ ] p95 abaixo de 200 ms em listagens de 100 itens, com filtros, busca e ordenação.
  - [ ] Desvios encontrados na medição preliminar da R2 corrigidos.

- [ ] **RT12 — Portabilidade**
  - [ ] Caminhos de arquivo montados com `pathlib`, sem separadores fixos (`\` ou `/`) e sem caminhos absolutos no código.
  - [ ] Nenhum comando, shell ou chamada dependente de sistema operacional (`os.system`, `cmd`, `powershell`) no código.
  - [ ] Arquivos de texto abertos com `encoding="utf-8"` explícito; o código não depende do tipo de fim de linha (CRLF ou LF).
  - [ ] Nomes de módulos e arquivos referenciados com a caixa exata (o Linux diferencia maiúsculas de minúsculas).
  - [ ] Testes independentes de sistema operacional: banco e arquivos temporários via `tmp_path`, sem caminhos fixos.
  - [ ] README traz os comandos de instalação e execução para Windows e para Linux.
  - [ ] A execução em Linux **não** é testada nem exigida no MVP; o objetivo é apenas não criar obstáculos a ela.

### Aceite da release R3 (critérios de sucesso do MVP)

- [ ] Todos os itens das releases R1, R2 e R3 concluídos.
- [ ] Todas as operações CRUD de grupos e tarefas funcionam conforme o contrato OpenAPI.
- [ ] Testes passam com cobertura de pelo menos 80%.
- [ ] A API sobe localmente com um único comando a partir de um ambiente limpo.
- [ ] Nenhum item fora de escopo (seção 6 do escopo) foi implementado.
