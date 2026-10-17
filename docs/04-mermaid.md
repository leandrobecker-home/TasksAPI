# Diagramas — Endpoints e Fluxo de Dados

| Item | Valor |
|---|---|
| Base | [02-backlog.md](02-backlog.md) v1.0 · [03-arquitetura-mvp.md](03-arquitetura-mvp.md) v1.0 |
| Versão do documento | 1.0 |
| Data | 2026-10-17 |

Os diagramas usam [Mermaid](https://mermaid.js.org/) e são renderizados direto no GitHub, GitLab e VS Code (com extensão de preview Mermaid). Caminhos de negócio são relativos a `/api/v1`.

## 1. Endpoints REST

Endpoints agrupados por recurso, com o ID do requisito e a release em que entram (R1 Core, R2 Piloto).

```mermaid
flowchart LR
    C([Cliente HTTP])

    subgraph G["/api/v1/task-groups"]
        G1["POST /task-groups<br/>RF01 · R1"]
        G2["GET /task-groups<br/>RF02 · R1"]
        G3["GET /task-groups/{id}<br/>RF03 · R1"]
        G4["PATCH /task-groups/{id}<br/>RF04 · R1"]
        G5["DELETE /task-groups/{id}<br/>RF05 · R1"]
        GT1["POST /task-groups/{group_id}/tasks<br/>RF06 · R1"]
        GT2["GET /task-groups/{group_id}/tasks<br/>RF07–RF10 · R1/R2"]
    end

    subgraph T["/api/v1/tasks"]
        T1["GET /tasks<br/>RF07–RF10 · R1/R2"]
        T2["GET /tasks/{id}<br/>RF11 · R1"]
        T3["PUT /tasks/{id}<br/>RF12 · R1"]
        T4["PATCH /tasks/{id}<br/>RF13 · R1"]
        T5["DELETE /tasks/{id}<br/>RF14 · R1"]
    end

    subgraph O["Operação (sem prefixo)"]
        O1["GET /health<br/>RF15 · R1"]
        O2["GET /docs<br/>RF16 · R2"]
    end

    C --> G
    C --> T
    C --> O
```

## 2. Arquitetura em camadas e fluxo de dados

Caminho de uma requisição pelas camadas definidas no RT02. Os schemas Pydantic ficam na borda HTTP; os modelos SQLModel, só no repositório.

```mermaid
flowchart TB
    C([Cliente HTTP])

    subgraph APP["Aplicação FastAPI (uvicorn)"]
        MW["Middlewares<br/>X-Request-ID · limite 1 MB · logs JSON<br/>RT09 · RT11"]
        R["Rotas<br/>validação com schemas Pydantic<br/>TaskCreate · TaskUpdate · TaskRead"]
        S["Serviços<br/>regras de negócio RN01–RN08"]
        REP["Repositórios<br/>modelos SQLModel"]
        EH["Exception handlers<br/>RFC 9457 Problem Details"]
    end

    DB[("SQLite<br/>task_groups · tasks")]

    C -- "requisição JSON" --> MW --> R
    R -- "dados validados" --> S
    S -- "consulta / persistência" --> REP
    REP -- "SQL" --> DB
    DB -- "linhas" --> REP
    REP -- "entidades" --> S
    S -- "resultado" --> R
    R -- "resposta JSON" --> MW --> C

    R -. "erro de validação 400/422" .-> EH
    S -. "erro de negócio 404/409/422" .-> EH
    EH -. "application/problem+json" .-> MW
```

## 3. Modelo de dados

```mermaid
erDiagram
    TASK_GROUP ||--o{ TASK : contem

    TASK_GROUP {
        uuid id PK
        string nome UK "1-100, único sem diferenciar maiúsculas"
        string descricao "até 500, opcional"
        datetime criado_em
        datetime atualizado_em
    }

    TASK {
        uuid id PK
        uuid task_group_id FK "obrigatório"
        string titulo "1-200"
        string descricao "até 2000, opcional"
        enum status "pendente | em_andamento | concluida"
        enum prioridade "baixa | media | alta"
        date data_vencimento "opcional"
        datetime criado_em
        datetime atualizado_em
        datetime concluido_em "gerado pelo servidor"
    }
```

## 4. Fluxos principais

### 4.1 Criar tarefa em um grupo (RF06, RN02)

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant R as Rota
    participant S as TaskService
    participant REP as Repositórios
    participant DB as SQLite

    C->>R: POST /task-groups/{group_id}/tasks
    R->>R: valida corpo (TaskCreate)
    alt corpo inválido
        R-->>C: 422 Problem Details
    end
    R->>S: criar_task(group_id, dados)
    S->>REP: buscar grupo(group_id)
    REP->>DB: SELECT task_groups
    DB-->>REP: grupo ou vazio
    alt grupo não existe (RN02)
        S-->>R: GrupoNaoEncontrado
        R-->>C: 404 Problem Details
    else grupo existe
        S->>S: aplica padrões e concluido_em (RN05, RN07)
        S->>REP: inserir task
        REP->>DB: INSERT tasks
        S-->>R: task criada
        R-->>C: 201 Created + Location
    end
```

### 4.2 Excluir grupo (RF05, RN03)

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant R as Rota
    participant S as TaskGroupService
    participant REP as Repositórios
    participant DB as SQLite

    C->>R: DELETE /task-groups/{id}
    R->>S: excluir_grupo(id)
    S->>REP: buscar grupo e contar tasks
    REP->>DB: SELECT task_groups / COUNT tasks
    alt grupo não existe
        R-->>C: 404 Problem Details
    else grupo possui tasks (RN03)
        R-->>C: 409 Conflict
    else grupo vazio
        S->>REP: excluir grupo
        REP->>DB: DELETE task_groups
        R-->>C: 204 No Content
    end
```

### 4.3 Ciclo de vida do status da tarefa (RN06, RN07)

```mermaid
stateDiagram-v2
    [*] --> pendente: criação (padrão)
    pendente --> em_andamento
    em_andamento --> pendente
    pendente --> concluida: preenche concluido_em
    em_andamento --> concluida: preenche concluido_em
    concluida --> pendente: limpa concluido_em
    concluida --> em_andamento: limpa concluido_em
    concluida --> [*]: DELETE /tasks/{id}
    pendente --> [*]: DELETE /tasks/{id}
    em_andamento --> [*]: DELETE /tasks/{id}
```
