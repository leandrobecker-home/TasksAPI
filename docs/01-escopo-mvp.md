# Escopo do MVP — Tasks API

| Item | Valor |
|---|---|
| Produto | Tasks API |
| Versão do documento | 1.4 |
| Data | 2026-10-17 |
| Status | Rascunho |

## 1. Objetivo

Disponibilizar uma API REST, desenvolvida em Python 3.14, que permita criar, consultar, atualizar e excluir grupos de tarefas (TaskGroups) e as tarefas (Tasks) organizadas sob eles. O MVP deve validar o modelo de dados e o contrato da API com o menor conjunto de funcionalidades que entregue valor, servindo de base para evoluções futuras (autenticação, multiusuário, integrações).

### 1.1 Critérios de sucesso

- Todas as operações CRUD de grupos e tarefas funcionam conforme o contrato documentado em OpenAPI.
- Os testes automatizados passam e cobrem no mínimo 80% do código da aplicação.
- A API sobe localmente com um único comando a partir de um ambiente limpo.

## 2. Glossário

| Termo | Definição |
|---|---|
| TaskGroup | Agrupador de tarefas, criado pelo usuário antes das tarefas que vai conter. |
| Task | Unidade de trabalho com título, status e metadados. Sempre pertence a um TaskGroup. |
| Status | Estado da tarefa no ciclo de vida: `pending`, `in_progress`, `completed`. |
| Prioridade | Grau de importância: `low`, `medium`, `high`. |

## 3. Modelo de dados

### 3.0 Convenção de nomes do contrato

O texto da documentação é em português, mas os identificadores do contrato da API e do código (campos, valores de enum e parâmetros de query) são em **inglês**. A tabela abaixo é a referência para quem lê os termos de domínio em português.

| Termo de domínio | Identificador |
|---|---|
| nome, descrição, título | `name`, `description`, `title` |
| nome normalizado (interno) | `normalized_name` |
| prioridade | `priority` |
| data de vencimento | `due_date` |
| criado em, atualizado em, concluído em | `created_at`, `updated_at`, `completed_at` |
| pendente, em andamento, concluída | `pending`, `in_progress`, `completed` |
| baixa, média, alta | `low`, `medium`, `high` |
| vencimento de, vencimento até (filtros) | `due_from`, `due_until` |

Mensagens de erro da API (`title` e `detail` do Problem Details) são em inglês.

### 3.1 Relacionamento

```text
TaskGroup 1 ──── 0..N Task
```

Um TaskGroup contém zero ou mais Tasks. Toda Task pertence a exatamente um TaskGroup.

### 3.2 Entidade `TaskGroup`

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `id` | UUID | Sim (gerado) | Gerado pelo servidor; imutável. |
| `name` | string | Sim | 1 a 100 caracteres; espaços nas pontas são removidos; único, sem diferenciar maiúsculas/minúsculas. |
| `normalized_name` | string | Sim (gerado) | Uso interno, não exposto na API. É o `name` após `strip` e `casefold()`, com índice único. Garante a RN01 também com acentos, pois o `lower()` do SQLite só trata ASCII. |
| `description` | string | Não | Até 500 caracteres. |
| `created_at` | datetime (UTC) | Sim (gerado) | Definido na criação; imutável. |
| `updated_at` | datetime (UTC) | Sim (gerado) | Atualizado a cada alteração. |

### 3.3 Entidade `Task`

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `id` | UUID | Sim (gerado) | Gerado pelo servidor; imutável. |
| `task_group_id` | UUID | Sim | Chave estrangeira para `TaskGroup.id`; o grupo precisa existir. |
| `title` | string | Sim | 1 a 200 caracteres; espaços nas pontas são removidos; não pode ficar vazio. |
| `description` | string | Não | Até 2000 caracteres. |
| `status` | enum | Sim | `pending` (padrão), `in_progress`, `completed`. |
| `priority` | enum | Sim | `low`, `medium` (padrão), `high`. |
| `due_date` | date (ISO 8601) | Não | Formato `YYYY-MM-DD`. |
| `created_at` | datetime (UTC) | Sim (gerado) | Definido na criação; imutável. |
| `updated_at` | datetime (UTC) | Sim (gerado) | Atualizado a cada alteração. |
| `completed_at` | datetime (UTC) | Não (gerado) | Preenchido quando `status` passa a `completed`; limpo se sair desse status. |

### 3.4 Regras de negócio

**TaskGroup**

- **RN01** — Não pode haver dois grupos com o mesmo `name` (comparação sem diferenciar maiúsculas/minúsculas, inclusive em letras acentuadas, via `normalized_name`). Tentativa de duplicar retorna `409 Conflict`, inclusive em requisições concorrentes (a garantia final é o índice único do banco).
- **RN02** — Uma Task só pode ser criada dentro de um TaskGroup existente. Não há Task sem grupo, nem grupo padrão criado implicitamente.
- **RN03** — Um grupo só pode ser excluído se não tiver tarefas. Se tiver, a exclusão retorna `409 Conflict`; o cliente deve excluir ou mover as tarefas antes.
- **RN04** — Uma Task pode ser movida para outro grupo alterando `task_group_id`. Se o grupo de destino não existir, a requisição retorna `422`.

**Task**

- **RN05** — Toda tarefa nasce com `status = pending`, salvo se outro valor válido for informado.
- **RN06** — Qualquer transição entre os três status é permitida.
- **RN07** — `completed_at` é controlado exclusivamente pelo servidor, conforme a transição de status para ou a partir de `completed`.
- **RN08** — Campos gerados pelo servidor (`id`, `created_at`, `updated_at`, `completed_at`) enviados no corpo são **ignorados**, sem erro. Qualquer outro campo desconhecido no corpo é **rejeitado** com `422`.

## 4. Requisitos funcionais

Os caminhos abaixo são relativos ao prefixo `/api/v1` (RNF04), exceto `/health` e `/docs`.

### 4.1 TaskGroups

| ID | Requisito | Endpoint |
|---|---|---|
| RF01 | Criar grupo. Retorna `201 Created` com o recurso criado e o header `Location`; `409` se o nome já existir. | `POST /task-groups` |
| RF02 | Listar grupos com paginação, busca por `name` (parâmetro `q`) e a quantidade de tarefas de cada grupo (`total_tasks`). | `GET /task-groups` |
| RF03 | Consultar grupo por `id`. Retorna `404` se não existir. | `GET /task-groups/{id}` |
| RF04 | Atualizar parcialmente um grupo (`name`, `description`). | `PATCH /task-groups/{id}` |
| RF05 | Excluir grupo vazio. Retorna `204 No Content`; `409` se houver tarefas (RN03); `404` se não existir. | `DELETE /task-groups/{id}` |

### 4.2 Tasks

A criação de tarefas acontece sempre sob um grupo (RN02). As operações sobre uma tarefa específica usam o caminho direto `/tasks/{id}`.

| ID | Requisito | Endpoint |
|---|---|---|
| RF06 | Criar tarefa no grupo informado no caminho. Retorna `201 Created` com o recurso criado e o header `Location`; `404` se o grupo não existir. | `POST /task-groups/{group_id}/tasks` |
| RF07 | Listar tarefas com paginação (`page`, `page_size`; padrão 20, máximo 100), de um grupo ou de todos os grupos. | `GET /task-groups/{group_id}/tasks`, `GET /tasks` |
| RF08 | Filtrar a listagem por `status`, `priority` e intervalo de `due_date` (`due_from`, `due_until`). Em `GET /tasks`, também por `task_group_id`. | `GET /task-groups/{group_id}/tasks`, `GET /tasks` |
| RF09 | Buscar texto em `title` e `description` (parâmetro `q`, sem diferenciar maiúsculas/minúsculas). | `GET /task-groups/{group_id}/tasks`, `GET /tasks` |
| RF10 | Ordenar a listagem por `created_at`, `due_date` ou `priority`, ascendente ou descendente (`sort=-created_at`). Padrão: `-created_at`. | `GET /task-groups/{group_id}/tasks`, `GET /tasks` |
| RF11 | Consultar tarefa por `id`. Retorna `404` se não existir. | `GET /tasks/{id}` |
| RF12 | Atualizar parcialmente uma tarefa (ex.: apenas `status`, ou `task_group_id` para mover de grupo, conforme RN04). | `PATCH /tasks/{id}` |
| RF13 | Excluir tarefa (exclusão física). Retorna `204 No Content`; `404` se não existir. | `DELETE /tasks/{id}` |

### 4.3 Operação

| ID | Requisito | Endpoint |
|---|---|---|
| RF14 | Expor verificação de saúde da aplicação e da conexão com o banco. | `GET /health` |
| RF15 | Expor documentação interativa gerada a partir da especificação OpenAPI. | `GET /docs` |

### 4.4 Formato da listagem

```json
{
  "items": [ { "id": "…", "task_group_id": "…", "title": "…", "status": "pending" } ],
  "page": 1,
  "page_size": 20,
  "total": 42
}
```

### 4.5 Formato de erro

Todas as respostas de erro seguem o padrão RFC 9457 (Problem Details):

```json
{
  "type": "about:blank",
  "title": "Validation Error",
  "status": 422,
  "detail": "title: must be between 1 and 200 characters",
  "instance": "/tasks"
}
```

| Código | Uso |
|---|---|
| `400` | JSON malformado ou parâmetro de **query** inválido (ex.: `page_size=abc`, `sort` desconhecido). |
| `404` | Recurso inexistente (inclusive o grupo informado no caminho) ou rota inexistente. |
| `405` | Método HTTP não permitido na rota. |
| `409` | Conflito com o estado atual: nome de grupo duplicado (RN01) ou exclusão de grupo com tarefas (RN03). |
| `413` | Corpo da requisição maior que 1 MB (RNF11). |
| `422` | Falha de validação do **corpo** ou de parâmetro de **caminho** (ex.: `id` que não é UUID), campo desconhecido (RN08) e `task_group_id` que não existe (RN04). |
| `500` | Erro interno não tratado (sem detalhes internos no corpo). |
| `503` | Serviço indisponível: `GET /health` com o banco fora do ar. |

O FastAPI devolve `422` por padrão para qualquer erro de validação. O mapeamento acima (`400` para query, `422` para corpo e caminho) exige um *exception handler* próprio (RNF14).

## 5. Requisitos não funcionais

| ID | Categoria | Requisito |
|---|---|---|
| RNF01 | Plataforma | Python 3.14, com ambiente e dependências gerenciados por `uv` (ver [PYTHON.md](PYTHON.md)). |
| RNF02 | Arquitetura | Separação em camadas: rotas (HTTP) → serviços (regras de negócio) → repositório (persistência). Regras de negócio não dependem do framework web. |
| RNF03 | Persistência | Banco relacional acessado via ORM e migrações versionadas. SQLite no MVP; troca para PostgreSQL sem alteração nas camadas de rota e serviço. No SQLite, chaves estrangeiras habilitadas em toda conexão (`PRAGMA foreign_keys=ON`, desligado por padrão). |
| RNF04 | Contrato | Especificação OpenAPI 3.x gerada a partir do código e versionada; API sob o prefixo `/api/v1`. |
| RNF05 | Formato | JSON em UTF-8; datas em ISO 8601; datetimes sempre em UTC. |
| RNF06 | Desempenho | p95 abaixo de 200 ms para operações unitárias e listagens de até 100 itens, com base de 10 mil tarefas, em ambiente local. |
| RNF07 | Qualidade | Testes unitários e de integração com `pytest`; cobertura mínima de 80%. |
| RNF08 | Padronização | Lint e formatação com `ruff`; checagem de tipos com `mypy` (ou equivalente) sem erros. |
| RNF09 | Observabilidade | Logs estruturados (JSON) com nível, timestamp, método, rota, status HTTP, duração e `request_id` (propagado no header `X-Request-ID`). |
| RNF10 | Configuração | Configuração por variáveis de ambiente (12-factor), com arquivo `.env.example` versionado. Nenhum segredo no repositório. |
| RNF11 | Segurança | Validação de toda entrada; limite de 1 MB no corpo da requisição, contado durante a leitura, inclusive quando o cliente não envia `Content-Length`; erros `500` não expõem stack trace. |
| RNF12 | Portabilidade | Desenvolvido e testado em Windows. O código é escrito para ser portável a Linux (`pathlib`, sem comandos ou caminhos dependentes do sistema operacional, `utf-8` explícito), mas a execução em Linux não é testada no MVP. O ambiente é gerenciado por `uv`. |
| RNF13 | Documentação | `README.md` com instruções de instalação, execução, testes e exemplos de requisição. |
| RNF14 | Tratamento de erros | Todas as respostas de erro, inclusive `404` de rota inexistente e `405`, usam `application/problem+json` (RFC 9457). *Exception handlers* próprios mapeiam erros de validação para `400` (query) ou `422` (corpo e caminho). |
| RNF15 | Estratégia de testes | Cada teste usa banco SQLite isolado (em memória ou arquivo temporário), sem depender da ordem de execução. Fixtures e fábricas de dados compartilhadas. Garantias do banco (chave estrangeira, unicidade do nome, fuso UTC) têm teste dedicado. |

### 5.1 Ferramentas de qualidade (RNF08)

| Ferramenta | Finalidade |
|---|---|
| `ruff` | Linter e formatador. Aponta erros e más práticas (imports e variáveis sem uso, `except:` genérico, nomes indefinidos), padroniza o estilo do código e ordena os imports. Corrige muitos problemas automaticamente (`ruff check --fix`). |
| `mypy` | Checador estático de tipos. Usa as anotações de tipo (`def f(x: int) -> str`) para encontrar inconsistências antes da execução, como passar `str` onde se espera `UUID` ou acessar atributo de um valor que pode ser `None`. |

As duas ferramentas analisam o código sem executá-lo e se complementam: o `ruff` cuida da limpeza e do padrão do código, e o `mypy`, da coerência dos tipos. Ambas devem rodar localmente antes de cada commit, e qualquer falha impede o commit.

```bash
uv run ruff check .    # lint
uv run ruff format .   # formatação
uv run mypy app        # checagem de tipos
```

## 6. Fora de escopo

Itens explicitamente excluídos do MVP. Podem ser reavaliados em versões futuras.

- Autenticação e autorização (login, JWT, OAuth, API keys).
- Multiusuário: donos de tarefas, atribuição, compartilhamento e permissões.
- Interface gráfica (web ou mobile).
- Subgrupos (hierarquia de TaskGroups) e Task em mais de um grupo.
- Exclusão em cascata de grupos com suas tarefas.
- Tags, categorias e subtarefas.
- Comentários, anexos e histórico de alterações (auditoria).
- Notificações e lembretes (e-mail, push, webhooks).
- Tarefas recorrentes.
- Exclusão lógica, lixeira e restauração.
- Operações em lote (criação, atualização ou exclusão em massa).
- Substituição integral de tarefa (`PUT /tasks/{id}`); a edição é feita por `PATCH`.
- Busca full-text avançada (relevância, stemming).
- Rate limiting, cache e alta disponibilidade.
- Conteinerização (Docker, `Dockerfile`, Docker Compose).
- Deploy em nuvem, pipelines de CI/CD e ambientes de homologação/produção.
- Integrações externas (calendários, Slack, Jira etc.).
- Internacionalização das mensagens de erro (MVP apenas em português).

## 7. Premissas e restrições

- A API é consumida por clientes confiáveis em ambiente controlado, o que justifica a ausência de autenticação no MVP. **Não expor publicamente nesta versão.**
- Volume esperado no MVP: até 10 mil tarefas e baixa concorrência.
- Não será usado nenhum pipeline de CI: a qualidade é garantida por um portão local (lint, formatação, tipos e testes com cobertura) executado antes de cada commit.
- Framework web e ORM serão definidos no documento de arquitetura, respeitando os RNF02, RNF03 e RNF04 e a compatibilidade com Python 3.14.

## 8. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Dependências ainda sem suporte pleno a Python 3.14 | Médio | Validar compatibilidade antes de fixar versões; manter lockfile (`uv.lock`). |
| Limitações de concorrência do SQLite | Baixo no MVP | Isolar acesso no repositório (RNF03) para migrar a PostgreSQL. |
| API sem autenticação | Alto se exposta | Restringir a ambiente local/rede interna; autenticação como primeiro item pós-MVP. |
| Semântica do SQLite: chave estrangeira desligada por padrão; `lower()` só trata ASCII | Alto | `PRAGMA foreign_keys=ON` em toda conexão; coluna `normalized_name` com `casefold()` e índice único; testes dedicados (RNF15). Ambos os problemas foram reproduzidos em spike. |
| Comportamento padrão do FastAPI diverge do contrato (`422` único, limite de corpo sem `Content-Length`) | Médio | *Exception handlers* e middleware próprios (RNF11, RNF14), com testes de contrato. Reproduzido em spike. |
| `httpx` com o `TestClient` do Starlette está descontinuado | Baixo | Usar `httpx2` (sem *warnings* em Python 3.14, verificado em spike). |
