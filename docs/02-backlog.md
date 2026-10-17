# Backlog do MVP — Tasks API

| Item | Valor |
|---|---|
| Base | [01-escopo-mvp.md](01-escopo-mvp.md) v1.1 |
| Versão do documento | 1.0 |
| Data | 2026-10-17 |
| Status | Rascunho |

## Convenções

- **RF**: requisito funcional. Os IDs são os mesmos do documento de escopo (seção 4).
- **RT**: requisito técnico. Cada RT corresponde ao RNF de mesmo número no escopo (seção 5); por exemplo, RT04 implementa o RNF04.
- **RN**: regra de negócio do escopo (seção 3.4), citada nos critérios que a validam.
- Caminhos de endpoint são relativos a `/api/v1`, exceto `/health` e `/docs`.
- Um item só é marcado como concluído quando **todos** os seus critérios de aceite estão marcados.

## Definição de pronto (vale para todo item)

- [ ] Critérios de aceite cobertos por testes automatizados (`pytest`) que passam.
- [ ] `ruff check`, `ruff format --check` e `mypy` sem erros.
- [ ] Respostas de erro no formato RFC 9457 (Problem Details), com os códigos da seção 4.5 do escopo.
- [ ] Código revisado por outra pessoa antes do merge.

## Visão geral das releases

| Release | Objetivo | RF | RT |
|---|---|---|---|
| R1 — Core | CRUD de grupos e tarefas funcionando de ponta a ponta. | RF01–RF07, RF11–RF15 | RT01, RT02, RT03, RT05, RT08, RT10 |
| R2 — Piloto | API utilizável por clientes do piloto: consulta avançada, documentação e operação. | RF08, RF09, RF10, RF16 | RT04, RT09, RT11, RT13 |
| R3 — Entrega final | Metas de qualidade, desempenho e portabilidade atingidas. | — | RT06, RT07, RT12 |

---

## R1 — Core

### Fundação técnica

- [ ] **RT01 — Plataforma Python 3.14 com `uv`**
  - [ ] `.python-version` contém `3.14` e está versionado.
  - [ ] `pyproject.toml` e `uv.lock` versionados; `uv sync` instala tudo a partir de um ambiente limpo.
  - [ ] `uv run python --version` retorna `Python 3.14.x`.
  - [ ] Um único comando documentado sobe a API localmente.

- [ ] **RT02 — Arquitetura em camadas**
  - [ ] Código separado em rotas, serviços e repositórios.
  - [ ] Serviços não importam nada do framework web (verificado em revisão ou por regra de import).
  - [ ] Regras de negócio (RN01–RN08) implementadas na camada de serviço e testadas sem subir o servidor HTTP.

- [ ] **RT03 — Persistência com ORM e migrações**
  - [ ] Tabelas `task_groups` e `tasks` criadas por migração versionada.
  - [ ] `tasks.task_group_id` é chave estrangeira obrigatória para `task_groups.id`.
  - [ ] Índice único em `nome` do grupo, sem diferenciar maiúsculas/minúsculas.
  - [ ] Banco SQLite configurado por variável de ambiente; nenhuma consulta SQL fora da camada de repositório.
  - [ ] Migrações aplicam e revertem sem erro em banco vazio.

- [ ] **RT05 — Formato de dados**
  - [ ] Requisições e respostas em JSON UTF-8 (`Content-Type: application/json`).
  - [ ] Datas no formato `YYYY-MM-DD`; datetimes em ISO 8601 com fuso UTC (`Z` ou `+00:00`).
  - [ ] Data em formato inválido retorna `422`.

- [ ] **RT08 — Lint, formatação e tipos**
  - [ ] Configuração de `ruff` e `mypy` no `pyproject.toml`.
  - [ ] `uv run ruff check .`, `uv run ruff format --check .` e `uv run mypy app` passam sem erros.
  - [ ] Pipeline de CI executa os três comandos e bloqueia o merge em caso de falha.

- [ ] **RT10 — Configuração por ambiente**
  - [ ] Toda configuração (URL do banco, nível de log, porta) lida de variáveis de ambiente.
  - [ ] `.env.example` versionado com todas as variáveis e valores de exemplo.
  - [ ] `.env` no `.gitignore`; nenhum segredo no repositório.

### TaskGroups

- [ ] **RF01 — Criar grupo** · `POST /task-groups`
  - [ ] Com `nome` válido, retorna `201`, o grupo criado e o header `Location: /api/v1/task-groups/{id}`.
  - [ ] `id`, `criado_em` e `atualizado_em` são gerados pelo servidor; valores enviados pelo cliente são ignorados.
  - [ ] Espaços nas pontas de `nome` são removidos antes de salvar.
  - [ ] `nome` ausente, vazio ou com mais de 100 caracteres retorna `422`.
  - [ ] `descricao` com mais de 500 caracteres retorna `422`.
  - [ ] `nome` já existente, inclusive com outra combinação de maiúsculas/minúsculas, retorna `409` (RN01).

- [ ] **RF02 — Listar grupos** · `GET /task-groups`
  - [ ] Retorna `200` no formato de listagem (`items`, `page`, `page_size`, `total`).
  - [ ] Paginação com padrão `page_size = 20` e máximo `100`; valor acima do máximo ou não positivo retorna `400`.
  - [ ] Parâmetro `q` filtra por `nome`, sem diferenciar maiúsculas/minúsculas.
  - [ ] Cada item traz `total_tasks` com a quantidade correta de tarefas do grupo.
  - [ ] Sem grupos cadastrados, retorna `items: []` e `total: 0`.

- [ ] **RF03 — Consultar grupo** · `GET /task-groups/{id}`
  - [ ] Grupo existente retorna `200` com todos os campos.
  - [ ] `id` inexistente retorna `404`.
  - [ ] `id` que não é UUID válido retorna `422`.

- [ ] **RF04 — Atualizar grupo** · `PATCH /task-groups/{id}`
  - [ ] Altera apenas os campos enviados (`nome`, `descricao`) e retorna `200` com o grupo atualizado.
  - [ ] `atualizado_em` muda; `criado_em` permanece igual.
  - [ ] Novo `nome` igual ao de outro grupo retorna `409` (RN01).
  - [ ] Mesmas validações de tamanho do RF01.
  - [ ] Grupo inexistente retorna `404`.

- [ ] **RF05 — Excluir grupo** · `DELETE /task-groups/{id}`
  - [ ] Grupo sem tarefas retorna `204` e deixa de ser encontrado (`GET` retorna `404`).
  - [ ] Grupo com ao menos uma tarefa retorna `409` e não é excluído (RN03).
  - [ ] Grupo inexistente retorna `404`.

### Tasks

- [ ] **RF06 — Criar tarefa no grupo** · `POST /task-groups/{group_id}/tasks`
  - [ ] Com `titulo` válido, retorna `201`, a tarefa criada e o header `Location: /api/v1/tasks/{id}`.
  - [ ] A tarefa criada tem `task_group_id` igual ao `group_id` do caminho.
  - [ ] `group_id` inexistente retorna `404`, e nenhuma tarefa é criada (RN02).
  - [ ] Sem `status` e `prioridade`, a tarefa nasce com `pendente` e `media` (RN05).
  - [ ] `titulo` ausente, vazio (após remover espaços) ou com mais de 200 caracteres retorna `422`.
  - [ ] `descricao` com mais de 2000 caracteres retorna `422`.
  - [ ] `status` ou `prioridade` fora dos valores permitidos retorna `422`.
  - [ ] Campos gerados (`id`, `criado_em`, `atualizado_em`, `concluido_em`) enviados pelo cliente são ignorados (RN08).
  - [ ] Criada já com `status = concluida`, a tarefa tem `concluido_em` preenchido (RN07).

- [ ] **RF07 — Listar tarefas** · `GET /task-groups/{group_id}/tasks`, `GET /tasks`
  - [ ] Retorna `200` no formato de listagem, com paginação igual à do RF02.
  - [ ] Pelo grupo, retorna apenas as tarefas daquele grupo.
  - [ ] `GET /tasks` retorna tarefas de todos os grupos.
  - [ ] `group_id` inexistente retorna `404`.
  - [ ] Ordem padrão: `criado_em` decrescente.

- [ ] **RF11 — Consultar tarefa** · `GET /tasks/{id}`
  - [ ] Tarefa existente retorna `200` com todos os campos, incluindo `task_group_id`.
  - [ ] `id` inexistente retorna `404`; `id` que não é UUID válido retorna `422`.

- [ ] **RF12 — Substituir tarefa** · `PUT /tasks/{id}`
  - [ ] Substitui todos os campos editáveis e retorna `200`.
  - [ ] Campo opcional omitido volta ao valor padrão ou nulo.
  - [ ] `task_group_id` é obrigatório; grupo inexistente retorna `422` (RN04).
  - [ ] Mesmas validações de campo do RF06.
  - [ ] Tarefa inexistente retorna `404`.

- [ ] **RF13 — Atualizar tarefa parcialmente** · `PATCH /tasks/{id}`
  - [ ] Altera apenas os campos enviados e retorna `200`; `atualizado_em` muda.
  - [ ] Qualquer transição entre `pendente`, `em_andamento` e `concluida` é aceita (RN06).
  - [ ] Mudar para `concluida` preenche `concluido_em`; sair de `concluida` limpa o campo (RN07).
  - [ ] `concluido_em` enviado pelo cliente é ignorado (RN08).
  - [ ] Alterar `task_group_id` para um grupo existente move a tarefa; para um grupo inexistente, retorna `422` (RN04).
  - [ ] Tarefa inexistente retorna `404`.

- [ ] **RF14 — Excluir tarefa** · `DELETE /tasks/{id}`
  - [ ] Tarefa existente retorna `204` e é removida fisicamente (`GET` retorna `404`).
  - [ ] Após excluir a última tarefa de um grupo, o grupo pode ser excluído (RF05).
  - [ ] Tarefa inexistente retorna `404`.

### Operação

- [ ] **RF15 — Health check** · `GET /health`
  - [ ] Retorna `200` com `{"status": "ok", "database": "ok"}` quando a aplicação e o banco respondem.
  - [ ] Com o banco indisponível, retorna `503` com `"database": "error"`.
  - [ ] Não exige o prefixo `/api/v1`.

### Aceite da release R1

- [ ] Todos os itens da R1 concluídos.
- [ ] Fluxo de ponta a ponta validado: criar grupo → criar tarefas → listar → concluir uma tarefa → excluir tarefas → excluir grupo.
- [ ] Não é possível criar uma tarefa sem um grupo existente, por nenhum endpoint.

---

## R2 — Piloto

### Consulta avançada

- [ ] **RF08 — Filtros da listagem de tarefas** · `GET /task-groups/{group_id}/tasks`, `GET /tasks`
  - [ ] `status` e `prioridade` filtram pelo valor exato; valor inválido retorna `400`.
  - [ ] `vencimento_de` e `vencimento_ate` filtram por intervalo fechado de `data_vencimento`.
  - [ ] `vencimento_de` posterior a `vencimento_ate` retorna `400`.
  - [ ] Em `GET /tasks`, `task_group_id` filtra pelo grupo.
  - [ ] Filtros combinados se somam (operador E) e `total` reflete o resultado filtrado.

- [ ] **RF09 — Busca textual** · `GET /task-groups/{group_id}/tasks`, `GET /tasks`
  - [ ] `q` encontra tarefas com o termo em `titulo` ou `descricao`, sem diferenciar maiúsculas/minúsculas.
  - [ ] `q` combina com filtros e paginação.
  - [ ] `q` vazio é tratado como ausente.

- [ ] **RF10 — Ordenação** · `GET /task-groups/{group_id}/tasks`, `GET /tasks`
  - [ ] `sort` aceita `criado_em`, `data_vencimento` e `prioridade`, com `-` para ordem decrescente.
  - [ ] Ordenação por `prioridade` segue a ordem `baixa` < `media` < `alta`, e não a ordem alfabética.
  - [ ] Campo de ordenação inválido retorna `400`.
  - [ ] Tarefas sem `data_vencimento` aparecem por último em qualquer direção.

### Contrato e documentação

- [ ] **RF16 — Documentação interativa** · `GET /docs`
  - [ ] `/docs` exibe todos os endpoints de grupos, tarefas e operação.
  - [ ] Cada endpoint documenta parâmetros, corpo, respostas de sucesso e de erro, com exemplos.
  - [ ] É possível executar requisições pela página.

- [ ] **RT04 — Contrato OpenAPI versionado**
  - [ ] Especificação OpenAPI 3.x gerada a partir do código, sem edição manual.
  - [ ] Arquivo da especificação versionado no repositório.
  - [ ] CI falha se o arquivo versionado estiver diferente do gerado pelo código.
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

- [ ] **RT11 — Validação e proteção de entrada**
  - [ ] Corpo maior que 1 MB retorna `413`.
  - [ ] JSON malformado retorna `400`.
  - [ ] Campos desconhecidos no corpo são rejeitados com `422`.
  - [ ] Erros `500` não expõem stack trace, SQL ou caminhos internos na resposta.

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
  - [ ] Índices necessários criados por migração (ex.: `task_group_id`, `status`, `data_vencimento`).

- [ ] **RT07 — Cobertura de testes**
  - [ ] Testes unitários dos serviços e testes de integração dos endpoints.
  - [ ] Todas as regras RN01–RN08 têm teste dedicado.
  - [ ] Cobertura de pelo menos 80%, medida com `pytest --cov`.
  - [ ] CI falha se a cobertura ficar abaixo de 80%.

- [ ] **RT12 — Portabilidade**
  - [ ] Suíte de testes passa em Windows e em Linux.
  - [ ] CI executa a suíte nos dois sistemas operacionais.
  - [ ] Nenhum caminho de arquivo ou comando dependente de sistema operacional no código.

### Aceite da release R3 (critérios de sucesso do MVP)

- [ ] Todos os itens das releases R1, R2 e R3 concluídos.
- [ ] Todas as operações CRUD de grupos e tarefas funcionam conforme o contrato OpenAPI.
- [ ] Testes passam com cobertura de pelo menos 80%.
- [ ] A API sobe localmente com um único comando a partir de um ambiente limpo.
- [ ] Nenhum item fora de escopo (seção 6 do escopo) foi implementado.
