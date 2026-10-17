# Instalação do Python 3.14 (isolada de outras versões)

Este guia usa o [uv](https://docs.astral.sh/uv/) para instalar o Python 3.14 **sem interferir** em versões do Python já instaladas no sistema. Os comandos são iguais no Windows e no Linux; só a instalação do `uv` muda.

## 1. Instalar o uv

**Windows (PowerShell):**

```powershell
winget install --id=astral-sh.uv -e
```

**Linux / macOS:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Feche e reabra o terminal e confirme:

```bash
uv --version
```

## 2. Instalar o Python 3.14

```bash
uv python install 3.14
```

O uv guarda essa instalação em um diretório próprio. Ela **não** altera o PATH nem substitui o `python` global. Para listar as versões gerenciadas pelo uv:

```bash
uv python list --only-installed
```

## 3. Fixar a versão no projeto

Na raiz do projeto:

```bash
uv python pin 3.14
```

Isso grava `3.14` no arquivo `.python-version`, que o uv usa para escolher o Python do projeto.

## 4. Criar o ambiente virtual

```bash
uv venv --python 3.14
```

Cria a pasta `.venv` com o Python 3.14, independentemente de outras versões instaladas globalmente.

## 5. Verificar a versão

```bash
uv run python --version          # deve mostrar Python 3.14.x
```

## 6. Ativação manual (opcional)

Só necessária se você preferir usar `python` diretamente.

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

Depois da ativação, `python` aponta para o 3.14 do projeto. Para sair, use `deactivate`.

## 7. Usar outra versão em um projeto

```bash
uv python install 3.13
uv python pin 3.13
uv venv --python 3.13
```

## Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `uv` não é reconhecido | Terminal aberto antes da instalação | Feche e reabra o terminal |
| `python --version` mostra outra versão | Está usando o Python global | Use `uv run python --version` ou ative o `.venv` |
| Erro ao ativar o venv no PowerShell | Política de execução bloqueia scripts | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` ou use apenas `uv run` |

## Arquivos que devem ficar no repositório

- `.python-version`

Adicione `.venv/` ao `.gitignore`.
