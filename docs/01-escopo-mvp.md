# Escopo do MVP — Tasks API

| Item | Valor |
|---|---|
| Produto | Tasks API |
| Versão do documento | 1.1 |
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
| Status | Estado da tarefa no ciclo de vida: `pendente`, `em_andamento`, `concluida`. |
| Prioridade | Grau de importância: `baixa`, `media`, `alta`. |

## 3. Modelo de dados

### 3.1 Relacionamento

```text
TaskGroup 1 ──── 0..N Task
```

Um TaskGroup contém zero ou mais Tasks. Toda Task pertence a exatamente um TaskGroup.

### 3.2 Entidade `TaskGroup`

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `id` | UUID | Sim (gerado) | Gerado pelo servidor; imutável. |
| `nome` | string | Sim | 1 a 100 caracteres; espaços nas pontas são removidos; único, sem diferenciar maiúsculas/minúsculas. |
| `descricao` | string | Não | Até 500 caracteres. |
| `criado_em` | datetime (UTC) | Sim (gerado) | Definido na criação; imutável. |
| `atualizado_em` | datetime (UTC) | Sim (gerado) | Atualizado a cada alteração. |

### 3.3 Entidade `Task`

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `id` | UUID | Sim (gerado) | Gerado pelo servidor; imutável. |
| `task_group_id` | UUID | Sim | Chave estrangeira para `TaskGroup.id`; o grupo precisa existir. |
| `titulo` | string | Sim | 1 a 200 caracteres; espaços nas pontas são removidos; não pode ficar vazio. |
| `descricao` | string | Não | Até 2000 caracteres. |
| `status` | enum | Sim | `pendente` (padrão), `em_andamento`, `concluida`. |
| `prioridade` | enum | Sim | `baixa`, `media` (padrão), `alta`. |
| `data_vencimento` | date (ISO 8601) | Não | Formato `YYYY-MM-DD`. |
| `criado_em` | datetime (UTC) | Sim (gerado) | Definido na criação; imutável. |
| `atualizado_em` | datetime (UTC) | Sim (gerado) | Atualizado a cada alteração. |
| `concluido_em` | datetime (UTC) | Não (gerado) | Preenchido quando `status` passa a `concluida`; limpo se sair desse status. |

### 3.4 Regras de negócio

**TaskGroup**

- **RN01** — Não pode haver dois grupos com o mesmo `nome` (comparação sem diferenciar maiúsculas/minúsculas). Tentativa de duplicar retorna `409 Conflict`.
- **RN02** — Uma Task só pode ser criada dentro de um TaskGroup existente. Não há Task sem grupo, nem grupo padrão criado implicitamente.
- **RN03** — Um grupo só pode ser excluído se não tiver tarefas. Se tiver, a exclusão retorna `409 Conflict`; o cliente deve excluir ou mover as tarefas antes.
- **RN04** — Uma Task pode ser movida para outro grupo alterando `task_group_id`. Se o grupo de destino não existir, a requisição retorna `422`.

**Task**

- **RN05** — Toda tarefa nasce com `status = pendente`, salvo se outro valor válido for informado.
- **RN06** — Qualquer transição entre os três status é permitida.
- **RN07** — `concluido_em` é controlado exclusivamente pelo servidor, conforme a transição de status para ou a partir de `concluida`.
- **RN08** — Campos gerados (`id`, `criado_em`, `atualizado_em`, `concluido_em`) são ignorados ou rejeitados quando enviados pelo cliente.

## 4. Requisitos funcionais

Os caminhos abaixo são relativos ao prefixo `/api/v1` (RNF04), exceto `/health` e `/docs`.

### 4.1 TaskGroups

| ID | Requisito | Endpoint |
|---|---|---|
| RF01 | Criar grupo. Retorna `201 Created` com o recurso criado e o header `Location`; `409` se o nome já existir. | `POST /task-groups` |
| RF02 | Listar grupos com paginação, busca por `nome` (parâmetro `q`) e a quantidade de tarefas de cada grupo (`total_tasks`). | `GET /task-groups` |
| RF03 | Consultar grupo por `id`. Retorna `404` se não existir. | `GET /task-groups/{id}` |
| RF04 | Atualizar parcialmente um grupo (`nome`, `descricao`). | `PATCH /task-groups/{id}` |
| RF05 | Excluir grupo vazio. Retorna `204 No Content`; `409` se houver tarefas (RN03); `404` se não existir. | `DELETE /task-groups/{id}` |

### 4.2 Tasks

A criação de tarefas acontece sempre sob um grupo (RN02). As operações sobre uma tarefa específica usam o caminho direto `/tasks/{id}`.

| ID | Requisito | Endpoint |
|---|---|---|
| RF06 | Criar tarefa no grupo informado no caminho. Retorna `201 Created` com o recurso criado e o header `Location`; `404` se o grupo não existir. | `POST /task-groups/{group_id}/tasks` |
| RF07 | Listar tarefas com paginação (`page`, `page_size`; padrão 20, máximo 100), de um grupo ou de todos os grupos. | `GET /task-groups/{group_id}/tasks`, `GET /tasks` |
| RF08 | Filtrar a listagem por `status`, `prioridade` e intervalo de `data_vencimento` (`vencimento_de`, `vencimento_ate`). Em `GET /tasks`, também por `task_group_id`. | `GET /task-groups/{group_id}/tasks`, `GET /tasks` |
| RF09 | Buscar texto em `titulo` e `descricao` (parâmetro `q`, sem diferenciar maiúsculas/minúsculas). | `GET /task-groups/{group_id}/tasks`, `GET /tasks` |
| RF10 | Ordenar a listagem por `criado_em`, `data_vencimento` ou `prioridade`, ascendente ou descendente (`sort=-criado_em`). Padrão: `-criado_em`. | `GET /task-groups/{group_id}/tasks`, `GET /tasks` |
| RF11 | Consultar tarefa por `id`. Retorna `404` se não existir. | `GET /tasks/{id}` |
| RF12 | Substituir integralmente uma tarefa (inclui `task_group_id`). | `PUT /tasks/{id}` |
| RF13 | Atualizar parcialmente uma tarefa (ex.: apenas `status`, ou `task_group_id` para mover de grupo, conforme RN04). | `PATCH /tasks/{id}` |
| RF14 | Excluir tarefa (exclusão física). Retorna `204 No Content`; `404` se não existir. | `DELETE /tasks/{id}` |

### 4.3 Operação

| ID | Requisito | Endpoint |
|---|---|---|
| RF15 | Expor verificação de saúde da aplicação e da conexão com o banco. | `GET /health` |
| RF16 | Expor documentação interativa gerada a partir da especificação OpenAPI. | `GET /docs` |

### 4.4 Formato da listagem

```json
{
  "items": [ { "id": "…", "task_group_id": "…", "titulo": "…", "status": "pendente" } ],
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
  "detail": "titulo: deve ter entre 1 e 200 caracteres",
  "instance": "/tasks"
}
```

| Código | Uso |
|---|---|
| `400` | Requisição malformada (JSON inválido, parâmetro de query inválido). |
| `404` | Recurso inexistente (inclusive o grupo informado no caminho). |
| `409` | Conflito com o estado atual: nome de grupo duplicado (RN01) ou exclusão de grupo com tarefas (RN03). |
| `422` | Falha de validação de campos, inclusive `task_group_id` que não existe (RN04). |
| `500` | Erro interno não tratado (sem detalhes internos no corpo). |

## 5. Requisitos não funcionais

| ID | Categoria | Requisito |
|---|---|---|
| RNF01 | Plataforma | Python 3.14, com ambiente e dependências gerenciados por `uv` (ver [PYTHON.md](PYTHON.md)). |
| RNF02 | Arquitetura | Separação em camadas: rotas (HTTP) → serviços (regras de negócio) → repositório (persistência). Regras de negócio não dependem do framework web. |
| RNF03 | Persistência | Banco relacional acessado via ORM e migrações versionadas. SQLite no MVP; troca para PostgreSQL sem alteração nas camadas de rota e serviço. |
| RNF04 | Contrato | Especificação OpenAPI 3.x gerada a partir do código e versionada; API sob o prefixo `/api/v1`. |
| RNF05 | Formato | JSON em UTF-8; datas em ISO 8601; datetimes sempre em UTC. |
| RNF06 | Desempenho | p95 abaixo de 200 ms para operações unitárias e listagens de até 100 itens, com base de 10 mil tarefas, em ambiente local. |
| RNF07 | Qualidade | Testes unitários e de integração com `pytest`; cobertura mínima de 80%. |
| RNF08 | Padronização | Lint e formatação com `ruff`; checagem de tipos com `mypy` (ou equivalente) sem erros. |
| RNF09 | Observabilidade | Logs estruturados (JSON) com nível, timestamp, método, rota, status HTTP, duração e `request_id` (propagado no header `X-Request-ID`). |
| RNF10 | Configuração | Configuração por variáveis de ambiente (12-factor), com arquivo `.env.example` versionado. Nenhum segredo no repositório. |
| RNF11 | Segurança | Validação de toda entrada; limite de tamanho do corpo da requisição (1 MB); erros `500` não expõem stack trace. |
| RNF12 | Portabilidade | Execução em Windows e Linux, diretamente no ambiente local gerenciado por `uv`. |
| RNF13 | Documentação | `README.md` com instruções de instalação, execução, testes e exemplos de requisição. |

### 5.1 Ferramentas de qualidade (RNF08)

| Ferramenta | Finalidade |
|---|---|
| `ruff` | Linter e formatador. Aponta erros e más práticas (imports e variáveis sem uso, `except:` genérico, nomes indefinidos), padroniza o estilo do código e ordena os imports. Corrige muitos problemas automaticamente (`ruff check --fix`). |
| `mypy` | Checador estático de tipos. Usa as anotações de tipo (`def f(x: int) -> str`) para encontrar inconsistências antes da execução, como passar `str` onde se espera `UUID` ou acessar atributo de um valor que pode ser `None`. |

As duas ferramentas analisam o código sem executá-lo e se complementam: o `ruff` cuida da limpeza e do padrão do código, e o `mypy`, da coerência dos tipos. Ambas devem rodar localmente e no CI, e qualquer falha bloqueia o merge.

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
- Busca full-text avançada (relevância, stemming).
- Rate limiting, cache e alta disponibilidade.
- Conteinerização (Docker, `Dockerfile`, Docker Compose).
- Deploy em nuvem, pipeline de CD e ambientes de homologação/produção.
- Integrações externas (calendários, Slack, Jira etc.).
- Internacionalização das mensagens de erro (MVP apenas em português).

## 7. Premissas e restrições

- A API é consumida por clientes confiáveis em ambiente controlado, o que justifica a ausência de autenticação no MVP. **Não expor publicamente nesta versão.**
- Volume esperado no MVP: até 10 mil tarefas e baixa concorrência.
- Framework web e ORM serão definidos no documento de arquitetura, respeitando os RNF02, RNF03 e RNF04 e a compatibilidade com Python 3.14.

## 8. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Dependências ainda sem suporte pleno a Python 3.14 | Médio | Validar compatibilidade antes de fixar versões; manter lockfile (`uv.lock`). |
| Limitações de concorrência do SQLite | Baixo no MVP | Isolar acesso no repositório (RNF03) para migrar a PostgreSQL. |
| API sem autenticação | Alto se exposta | Restringir a ambiente local/rede interna; autenticação como primeiro item pós-MVP. |
