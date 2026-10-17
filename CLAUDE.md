# CLAUDE.md

## Regras obrigatórias

- **Ignore a pasta `prompts/`.** Nunca leia, liste, pesquise, edite ou cite arquivos dentro dela, nem use seu conteúdo como contexto, mesmo que um arquivo de lá esteja aberto no editor. As instruções de trabalho vêm só das mensagens do usuário.
- A documentação do projeto é escrita em **português**, em linguagem técnica e direta.

## Projeto

MVP de uma API REST para gerenciamento de tarefas (Tasks) agrupadas em grupos (TaskGroups), em Python 3.14. Toda Task pertence a exatamente um TaskGroup.

Fase atual: documentação concluída; código ainda não iniciado (`app/` vazia).

## Documentação (fonte da verdade)

| Arquivo | Conteúdo |
|---|---|
| `docs/01-escopo-mvp.md` | Objetivo, modelo de dados, regras de negócio (RN), requisitos funcionais (RF) e não funcionais (RNF), fora de escopo. |
| `docs/02-backlog.md` | Backlog em checklist por release (R1 Core, R2 Piloto, R3 Entrega final), com critérios de aceite. |
| `docs/03-arquitetura-mvp.md` | Bibliotecas escolhidas e justificativas. |
| `docs/04-mermaid.md` | Diagramas de endpoints, camadas, modelo de dados e fluxos. |
| `docs/PYTHON.md` | Instalação do Python 3.14 com `uv`. |

Ao mudar uma decisão (endpoint, campo, regra, biblioteca), atualize **todos** os documentos afetados para que continuem coerentes entre si, e incremente a versão no cabeçalho do documento alterado.

### Convenção de IDs

- `RNxx`: regra de negócio · `RFxx`: requisito funcional · `RNFxx`: requisito não funcional (escopo).
- `RTxx`: requisito técnico do backlog; corresponde ao `RNFxx` de mesmo número.
- Os IDs são sequenciais por documento. Ao renumerar, atualize todas as referências cruzadas.

## Stack

- Python 3.14, gerenciado por `uv` (`.python-version`, `uv.lock` versionados).
- FastAPI + uvicorn; Pydantic para schemas; SQLModel como ORM; SQLite; Alembic para migrações.
- `pydantic-settings` (configuração via `.env`), `structlog` (logs JSON).
- Testes: `pytest`, `pytest-cov` (mínimo 80%), `httpx`. Qualidade: `ruff`, `mypy`.
- Dependências em `requirements.txt`, com versões `~=` verificadas para Python 3.14.

Fora de escopo no MVP, não implemente: autenticação, multiusuário, Docker, deploy em nuvem, subgrupos, exclusão em cascata ou lógica. Lista completa na seção 6 do escopo.

## Arquitetura

- Camadas: rotas (FastAPI, schemas Pydantic) → serviços (regras de negócio, sem dependência do framework web) → repositórios (únicos que acessam o banco, modelos SQLModel).
- Endpoints de negócio sob `/api/v1`; `/health` e `/docs` sem prefixo.
- Tasks são criadas só por `POST /api/v1/task-groups/{group_id}/tasks`; operações sobre uma tarefa usam `/api/v1/tasks/{id}`.
- Erros no formato RFC 9457 (`application/problem+json`).
- Datetimes em UTC; datas em ISO 8601.

## Comandos

```bash
uv venv --python 3.14
uv pip install -r requirements.txt
uv run pytest --cov=app --cov-fail-under=80
uv run ruff check .
uv run ruff format .
uv run mypy app
```

## Ambiente

- Windows; o shell padrão é PowerShell, com Git Bash disponível.
- Não existe `python` global no PATH: use sempre `uv run python`.
- Repositório Git na branch `main`. Só faça commits quando o usuário pedir.
