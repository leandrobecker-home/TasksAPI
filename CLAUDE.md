# CLAUDE.md

## Regras obrigatórias

- **Não consuma a pasta `prompts/`.** Durante as tarefas solicitadas, nunca leia, liste, pesquise, edite ou cite arquivos dentro dela, nem use seu conteúdo como contexto, mesmo que um arquivo de lá esteja aberto no editor. As instruções de trabalho vêm só das mensagens do usuário.
  - **Exceção: operações de Git.** É permitido acessar `prompts/` para versionamento (`git add`, `git commit`, `git status`, `git log`, `git diff --stat`), pois a pasta faz parte do repositório. Mesmo nesses casos, não abra nem leia o conteúdo dos arquivos.
- A documentação do projeto é escrita em **português**, em linguagem técnica e direta, e os arquivos de `docs/` são gerados por Claude. Edições feitas diretamente pelo usuário nesses arquivos podem ser ignoradas: não as preserve nem as comente, e regenere o conteúdo quando precisar.
- **Aprovação antes de cada commit.** Antes de qualquer commit (inclusive `docs`, `docs(prompts)`, renomeações e tags), apresente os arquivos que entrarão, a mensagem completa e o resultado do portão de qualidade, e **aguarde a aprovação explícita**. A aprovação vale só para aquele commit. Detalhes em `docs/07-passos-dev.md`, seção 1.4. Não faça `git push` sem pedido.
- **Código em inglês.** Na etapa de codificação, todo o código-fonte deve ser gerado em inglês: nomes de módulos, classes, funções, variáveis e campos, docstrings, comentários, mensagens de log e mensagens de erro da API. Isso vale para os arquivos em `app/` e `tests/`. A documentação em `docs/` continua em português.
  - O contrato da API já está definido em inglês nos documentos (ver seção 3.0 do escopo): `name`, `description`, `title`, `priority`, `due_date`, `created_at`, `updated_at`, `completed_at`; status `pending`, `in_progress`, `completed`; prioridades `low`, `medium`, `high`; filtros `due_from` e `due_until`. Use exatamente esses identificadores. As mensagens de erro da API também são em inglês.

## Projeto

MVP de uma API REST para gerenciamento de tarefas (Tasks) agrupadas em grupos (TaskGroups), em Python 3.14. Toda Task pertence a exatamente um TaskGroup.

Fase atual: implementação da R1 em andamento, seguindo `docs/07-passos-dev.md`. Etapas 1 a 9 concluídas (esqueleto, configuração, qualidade local, infraestrutura de testes, aplicação mínima, erros e paginação, persistência de TaskGroup, CRUD completo em `/api/v1/task-groups` e persistência de Task, com a recusa de excluir grupo que tem tarefas). Próxima: Etapa 10 (regras e endpoints de Task).

## Documentação (fonte da verdade)

| Arquivo | Conteúdo |
|---|---|
| `docs/01-escopo-mvp.md` | Objetivo, modelo de dados, regras de negócio (RN), requisitos funcionais (RF) e não funcionais (RNF), fora de escopo. |
| `docs/02-backlog.md` | Backlog em checklist por release (R1 Core, R2 Piloto, R3 Entrega final), com critérios de aceite. |
| `docs/03-arquitetura-mvp.md` | Bibliotecas escolhidas e justificativas. |
| `docs/04-mermaid.md` | Diagramas de endpoints, camadas, modelo de dados e fluxos. |
| `docs/07-passos-dev.md` | Plano de implementação em etapas numeradas, com testes e commits atômicos (Conventional Commits). Siga-o ao codificar. |
| `docs/PYTHON.md` | Instalação do Python 3.14 com `uv`. |

Ao mudar uma decisão (endpoint, campo, regra, biblioteca), atualize **todos** os documentos afetados para que continuem coerentes entre si, e incremente a versão no cabeçalho do documento alterado.

### Convenção de IDs

- `RNxx`: regra de negócio · `RFxx`: requisito funcional · `RNFxx`: requisito não funcional (escopo).
- `RTxx`: requisito técnico do backlog; corresponde ao `RNFxx` de mesmo número.
- Os IDs são sequenciais por documento. Ao renumerar, atualize todas as referências cruzadas.

## Stack

- Python 3.14, gerenciado por `uv` (`.python-version`, `uv.lock` versionados).
- FastAPI + uvicorn; Pydantic para schemas; SQLModel como ORM; SQLite; Alembic para migrações (só a partir da R2; na R1 usa `create_all`).
- `pydantic-settings` (configuração via `.env`), `structlog` (logs JSON).
- Testes: `pytest`, `pytest-cov` (mínimo 80%), `httpx2` (não `httpx`: o Starlette emite aviso de descontinuação). Qualidade: `ruff`, `mypy`.
- Dependências em `requirements.txt`, com versões `~=` verificadas para Python 3.14.

Fora de escopo no MVP, não implemente: autenticação, multiusuário, Docker, deploy em nuvem, subgrupos, exclusão em cascata ou lógica, `PUT /tasks/{id}` (edição é só por `PATCH`). Lista completa na seção 6 do escopo.

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
uv run python -m app
uv run ruff check .
uv run ruff format .
uv run mypy app
```

## Ambiente

- Windows; o shell padrão é PowerShell, com Git Bash disponível.
- Não existe `python` global no PATH: use sempre `uv run python`.
- O `uv` foi instalado com o winget, mas o terminal pode não enxergá-lo. Se `uv` não for encontrado, abra um novo terminal; se persistir, adicione a pasta de instalação ao PATH da sessão (PowerShell): `$env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe;$env:Path"`.
- Repositório Git local na branch `main`. Não será usado nenhum pipeline de CI: o portão de qualidade (`ruff format`, `ruff check`, `mypy app`, `pytest --cov`) roda só localmente antes de cada commit. Só faça commits quando o usuário pedir.

## Armadilhas já verificadas (spike de 2026-10-17)

- SQLite: `PRAGMA foreign_keys=ON` em toda conexão (vem desligado). Unicidade de `TaskGroup.name` via coluna `normalized_name` (`strip` + `casefold`) com índice único, pois `lower()` do SQLite só trata ASCII.
- Erros de validação: `400` para query, `422` para corpo e caminho (exige `exception_handler`; o padrão do FastAPI é `422` para tudo).
- RN08: campos gerados no corpo são ignorados; qualquer outro campo desconhecido é `422`.
- Limite de 1 MB: contar bytes durante a leitura; checar só `Content-Length` não bloqueia corpo em *chunks*.
- Datetimes UTC fazem ida e volta no SQLite sem perder o fuso.
