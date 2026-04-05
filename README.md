# perform-ai

Serviço de análise de complexidade de Pull Requests via **Dual-LLM + RAG**.

Recebe diffs do GitHub, resume com um LLM rápido (Gemini Flash), busca exemplos similares no Qdrant e gera um score de 0–100 com um LLM poderoso (Gemini Pro). Aprende continuamente com o feedback dos Tech Leads.

---

## Arquitetura

```
PR diff
  └─ Preprocessor (remove ruído, lock files, imports)
       └─ LLM Reader / Gemini Flash (resume o diff em linguagem técnica)
            └─ Embedding (sentence-transformers, local, 384 dims)
                 └─ Qdrant RAG (busca Top 3 exemplos similares com score conhecido)
                      └─ LLM Scorer / Gemini Pro (decide score 0-100 com contexto)
                           └─ Resultado: score, confiança, justificativa
```

Se a confiança for baixa (`< 0.7`), a análise é marcada como `doubtful` e enviada para revisão humana. A correção do Tech Lead é reinserida no Qdrant como novo exemplo de calibração.

---

## Pré-requisitos

- Python 3.11+
- Docker (para o Qdrant)
- Chave de API do [Google Gemini](https://aistudio.google.com/apikey)

---

## Setup

### 1. Variáveis de ambiente

```bash
cp .env.example .env
```

Editar `.env`:

```env
GEMINI_API_KEY=sua_chave_aqui
QDRANT_URL=http://localhost:6333
LLM_READER_MODEL=gemini-2.0-flash
LLM_SCORER_MODEL=gemini-2.0-flash
CONFIDENCE_THRESHOLD=0.7
```

### 2. Subir o Qdrant (banco vetorial)

```bash
docker-compose up qdrant -d
```

Sem conta, sem cloud — roda 100% local. Dados persistidos em volume Docker.

### 3. Instalar dependências Python

```bash
pip install .
```

Ou com `uv`:

```bash
uv sync
```

### 4. Rodar o serviço

```bash
uvicorn app.main:app --reload --port 8000
```

Na primeira execução, o modelo de embedding (`all-MiniLM-L6-v2`, ~90MB) é baixado automaticamente e cacheado.

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Status do serviço, Qdrant e modelo |
| `POST` | `/api/v1/analyze-pr` | Analisa uma PR e retorna score de complexidade |
| `POST` | `/api/v1/feedback` | Envia correção humana para o Qdrant |
| `POST` | `/api/v1/gold-set` | Adiciona exemplo curado ao Gold Set |
| `GET` | `/api/v1/gold-set` | Lista todos os exemplos do Qdrant |
| `DELETE` | `/api/v1/gold-set/{id}` | Remove um exemplo |

Documentação interativa disponível em `http://localhost:8000/docs` (Swagger UI).

---

## Exemplo de uso

```bash
curl -X POST http://localhost:8000/api/v1/analyze-pr \
  -H "Content-Type: application/json" \
  -d '{
    "pr_id": "uuid-da-pr",
    "title": "feat: implement payment retry logic",
    "body": "Adds exponential backoff for failed payment attempts",
    "diff": "diff --git a/src/payments/retry.ts ...",
    "author": "dev-login",
    "repo_full_name": "org/repo",
    "pr_number": 42,
    "additions": 120,
    "deletions": 15,
    "changed_files": 3
  }'
```

Resposta:

```json
{
  "score": 68,
  "confidence": 0.84,
  "difficulty_label": "hard",
  "justification": "Implementa lógica de retry com backoff exponencial em camada crítica de pagamentos...",
  "technical_summary": "...",
  "technologies": ["TypeScript"],
  "requires_review": false,
  "processing_time_ms": 4200
}
```

---

## Estrutura

```
perform-ai/
  app/
    main.py               # FastAPI app, CORS, lifespan
    config.py             # Configurações via .env
    models/
      enums.py            # DifficultyLabel, ChangeType, etc.
      schemas.py          # Pydantic models (request/response)
    utils/
      diff_parser.py      # Parse de unified diffs do GitHub
      text_cleaner.py     # Remoção de ruído (imports, comentários, etc.)
    services/
      preprocessor.py     # Orquestra limpeza do diff
      embedding_service.py # sentence-transformers local
      qdrant_service.py   # CRUD no banco vetorial
      llm_reader.py       # LLM 1 — resumo técnico (Gemini Flash)
      llm_scorer.py       # LLM 2 — score final com RAG (Gemini Pro)
      rag_pipeline.py     # Pipeline completo
    routers/
      analysis.py         # POST /analyze-pr
      feedback.py         # POST /feedback
      gold_set.py         # CRUD /gold-set
      health.py           # GET /health
  docker-compose.yml      # Qdrant + FastAPI
  pyproject.toml
  Dockerfile
  .env.example
```

---

## Gold Set

O Gold Set são exemplos curados manualmente que servem como referência de calibração para o scorer. **Quanto mais exemplos, maior a precisão.**

Recomendado: inserir ao menos **20–30 exemplos** cobrindo todos os níveis (trivial → expert) antes de usar em produção.

```bash
curl -X POST http://localhost:8000/api/v1/gold-set \
  -H "Content-Type: application/json" \
  -d '{
    "code_snippet": "...",
    "difficulty_score": 75,
    "difficulty_label": "hard",
    "technology": "TypeScript",
    "change_type": "feature",
    "description": "Implementação de cache distribuído com Redis e invalidação por evento"
  }'
```
