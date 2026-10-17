# Arquitetura do MVP — Bibliotecas Python

| Item | Valor |
|---|---|
| Base | [01-escopo-mvp.md](01-escopo-mvp.md) v1.3 · [02-backlog.md](02-backlog.md) v1.2 |
| Versão do documento | 1.2 |
| Data | 2026-10-17 |
| Status | Rascunho |

## 1. Objetivo

Definir as bibliotecas Python da implementação do MVP, justificando cada uma pelos itens do backlog (RF/RT) que atende. A lista de dependências fica em [`requirements.txt`](../requirements.txt).

## 2. Stack obrigatória

| Componente | Escolha | Papel |
|---|---|---|
| Linguagem | Python 3.14 | Gerenciado por `uv` (ver [PYTHON.md](PYTHON.md)). |
| Servidor HTTP | `uvicorn` | Executa a aplicação ASGI. |
| Framework REST | `FastAPI` | Rotas, injeção de dependências, validação de entrada e OpenAPI. |
| Banco de dados | SQLite | Arquivo local, acessado pelo módulo `sqlite3` da biblioteca padrão. |
| Modelagem | `pydantic` + `SQLModel` | Modelos de dados e mapeamento objeto-relacional. |

### 2.1 Modelagem com Pydantic e SQLModel

A modelagem ORM é feita com Pydantic por meio do **SQLModel**. Um modelo SQLModel é, ao mesmo tempo, um modelo Pydantic e uma tabela SQLAlchemy:

```python
class TaskGroup(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=100)
```

- **Modelos de tabela** (`table=True`): persistência, usados apenas na camada de repositório.
- **Schemas de entrada e saída** (`TaskCreate`, `TaskUpdate`, `TaskRead`): modelos Pydantic puros, usados nas rotas. Eles impedem que o cliente envie campos gerados pelo servidor (RN08) e permitem regras diferentes para `POST`, `PUT` e `PATCH`.

O SQLModel é mantido pelo mesmo autor do FastAPI e se integra a ele sem conversões manuais.

## 3. Bibliotecas da aplicação

| Biblioteca | Versão | Finalidade | Atende |
|---|---|---|---|
| `fastapi` | `~=0.143.3` | Define os endpoints REST, valida parâmetros e corpo e gera a especificação OpenAPI e a página `/docs` automaticamente. | RF01–RF15, RT04 |
| `uvicorn[standard]` | `~=0.54.0` | Servidor ASGI. O extra `standard` inclui `httptools` (parser HTTP mais rápido), `uvloop` (apenas Linux), `watchfiles` (recarga automática em desenvolvimento) e `python-dotenv`. | RT01, RT12 |
| `pydantic` | `~=2.14` | Tipos e validações dos schemas: tamanhos de campo, enums de `status` e `priority`, UUID, datas ISO 8601, rejeição de campos desconhecidos (`extra="forbid"`). | RT05, RT11, RN05, RN08 |
| `pydantic-settings` | `~=2.16` | Lê a configuração (URL do banco, nível de log, porta) de variáveis de ambiente e do arquivo `.env`, com validação de tipos. | RT10 |
| `sqlmodel` | `~=0.0.48` | ORM sobre SQLAlchemy com modelos Pydantic. Instala o `sqlalchemy` como dependência. Usado apenas na camada de repositório. | RT02, RT03 |
| `alembic` | `~=1.20` | Migrações versionadas (a partir da R2; na R1 o esquema é criado com `create_all`): tabelas, chave estrangeira `task_group_id`, índice único de `normalized_name` e índices de desempenho. Requer modo *batch* no SQLite. | RT03 (parte 2), RT06 |
| `structlog` | `~=26.1` | Logs estruturados em JSON. O `request_id` é associado ao contexto da requisição (`contextvars`) e aparece em todas as linhas de log dela. | RT09 |

## 4. Bibliotecas de desenvolvimento e testes

| Biblioteca | Versão | Finalidade | Atende |
|---|---|---|---|
| `pytest` | `~=9.1` | Execução dos testes unitários (serviços) e de integração (endpoints). | RT07 |
| `pytest-cov` | `~=7.1` | Mede a cobertura e faz o CI falhar abaixo de 80% (`--cov-fail-under=80`). | RT07 |
| `httpx2` | `~=2.13.1` | Cliente HTTP do `TestClient` do FastAPI e do script de carga. Substitui o `httpx`: o Starlette emite aviso de descontinuação ao usar `httpx` com o `TestClient`. | RT06, RT15 |
| `ruff` | `~=0.17.1` | Lint e formatação do código. | RT08 |
| `mypy` | `~=2.4` | Checagem estática de tipos. | RT08 |

## 5. Requisitos atendidos sem biblioteca adicional

Alguns itens do backlog não justificam uma dependência nova e serão implementados com FastAPI, Starlette (incluída no FastAPI) ou a biblioteca padrão.

| Requisito | Implementação |
|---|---|
| Banco SQLite (RT03) | Módulo `sqlite3` da biblioteca padrão, usado pelo SQLAlchemy. Não há pacote a instalar. |
| Erros no padrão RFC 9457 | Exception handlers do FastAPI que devolvem `application/problem+json`. |
| `X-Request-ID` (RT09) | Middleware próprio: reaproveita o header recebido ou gera um UUID. |
| Limite de 1 MB no corpo (RT11) | Middleware próprio que retorna `413` acima do limite. |
| Health check (RF14) | Rota que executa `SELECT 1` no banco. |
| Script de carga e p95 (RT06) | Script com `httpx2` assíncrono e `statistics.quantiles` da biblioteca padrão. |
| Paginação, filtros e ordenação (RF07–RF10) | Parâmetros de query do FastAPI e consultas SQLModel. |

## 6. Compatibilidade com Python 3.14

Verificado no PyPI em 2026-10-17: todas as versões listadas declaram suporte a Python 3.14. As dependências compiladas (`pydantic-core`, `httptools`, `uvloop`) publicam wheels `cp314` para Windows e Linux, quando aplicável. Isso atende ao risco "Dependências ainda sem suporte pleno a Python 3.14" do escopo (seção 8).

### 6.1 Política de versões

- O operador `~=` (compatible release) aceita correções e bloqueia saltos de versão com possíveis quebras. Exemplos: `~=2.14` aceita `2.15`, mas não `3.0`; `~=0.143.3` aceita `0.143.9`, mas não `0.144.0`.
- Bibliotecas na série `0.x` (`fastapi`, `uvicorn`, `sqlmodel`, `ruff`) têm a versão fixada até o patch, porque nelas mudanças de versão menor podem quebrar compatibilidade.
- As versões exatas instaladas, incluindo as dependências transitivas, devem ficar registradas no lockfile (`uv.lock`) versionado.

### 6.2 Verificação em ambiente real (spike)

Em 2026-10-17, em ambiente isolado (`uv` 0.13.1, CPython 3.14.8, Windows 11):

- `uv pip install -r requirements.txt` resolveu e instalou 43 pacotes sem erro, incluindo `sqlmodel 0.0.48` com `sqlalchemy 2.1.5` e `pydantic-core 2.50.1`.
- Os modelos SQLModel (tabela, chave estrangeira, índice) criaram o esquema no SQLite sem erro.
- O `TestClient` do FastAPI funciona com `httpx2` sem *warnings* (`-W error::DeprecationWarning`). Com `httpx`, o Starlette emite `StarletteDeprecationWarning`.
- O Alembic em modo *batch* e o `uvicorn` rodando de fato **não** foram exercitados; ficam como verificação do RT03 (parte 2) e do RT01.

### 6.3 Riscos técnicos reproduzidos no spike

| Risco | Resultado | Tratamento |
|---|---|---|
| Chave estrangeira no SQLite | Sem `PRAGMA foreign_keys=ON`, tarefa com grupo inexistente é **aceita**. Com o PRAGMA, é rejeitada. | `PRAGMA` em toda conexão (RT03). |
| Unicidade de `name` sem diferenciar caixa | Índice em `lower(name)` barra `Trabalho`/`trabalho`, mas **aceita** `Ação` e `AÇÃO`: o `lower()` do SQLite só trata ASCII. | Coluna `normalized_name` (`strip` + `casefold`) com índice único (RT03). |
| Fuso dos datetimes | **Não é problema**: o valor gravado em UTC volta com `tzinfo=UTC` no SQLModel + SQLAlchemy 2.1. | Mantido teste de ida e volta (RT03). |
| `400` para query e `422` para corpo | O padrão do FastAPI devolve `422` para tudo. Um `exception_handler` que inspeciona a origem do erro (`query`, `path`, `body`) resolve. | Handler próprio (RT14). |
| Campos gerados no corpo (RN08) | `extra="forbid"` com um `model_validator(mode="before")` que descarta apenas `id`, `created_at`, `updated_at` e `completed_at` ignora esses quatro e rejeita qualquer outro com `422`. | Padrão nos schemas de entrada (RF01, RF06, RF12). |
| Limite de 1 MB | Um middleware que só lê `Content-Length` devolve `413` com o cabeçalho, mas **deixa passar** o corpo de 1,1 MB enviado em *chunks* sem ele. | Contar os bytes durante a leitura do corpo (RT11). |

## 7. Instalação

Com o ambiente criado conforme [PYTHON.md](PYTHON.md):

```bash
uv venv --python 3.14
uv pip install -r requirements.txt
```

Para registrar as dependências no `pyproject.toml` e gerar o `uv.lock`:

```bash
uv add -r requirements.txt
```

## 8. Alternativas descartadas

| Alternativa | Motivo |
|---|---|
| SQLAlchemy puro | Exigiria duplicar cada entidade em modelo ORM e schema Pydantic. O SQLModel unifica as duas coisas e atende ao requisito de modelagem com Pydantic. |
| Tortoise ORM, Peewee | Menor integração com Pydantic e FastAPI; sem ganho para o MVP. |
| `python-json-logger` | Atende os logs JSON, mas sem o contexto por requisição que o `structlog` oferece. |
| `httpx` | Starlette emite aviso de descontinuação ao usá-lo com o `TestClient`; trocado por `httpx2`. |
| `asgi-correlation-id` | Um middleware de poucas linhas resolve o `X-Request-ID` sem dependência extra. |
| `locust` | Ferramenta de carga completa demais para medir p95 local; um script com `httpx2` basta. |
| Separar `requirements-dev.txt` | Sem deploy no escopo, um único arquivo com seções simplifica o MVP. Pode ser separado quando houver deploy. |
