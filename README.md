# artemis-ai

Serviço de análise de complexidade de Pull Requests via **Dual-LLM + RAG**.

Recebe diffs do GitHub, resume com um LLM (Gemini Flash), busca exemplos similares no Qdrant e gera um score de 0–100 com um segundo LLM (Gemini Pro). Se o Gemini estiver indisponível ou com quota esgotada, cai automaticamente para um **LLM local via Ollama** (DeepSeek Coder). Aprende continuamente com o feedback dos Tech Leads.

---

## Arquitetura

```
PR diff
  └─ Preprocessor (remove ruído, lock files, imports)
       └─ LLM Reader — Gemini Flash (resume o diff em linguagem técnica)
            │   fallback: Ollama / deepseek-coder (local)
            └─ Embedding (sentence-transformers all-MiniLM-L6-v2, local, 384 dims)
                 └─ Qdrant RAG (busca Top 3 exemplos similares com score conhecido)
                      └─ LLM Scorer — Gemini Pro (score 0-100 com contexto RAG)
                           │   fallback: Ollama / deepseek-coder (local)
                           └─ Resultado: score, confiança, justificativa, label
```

### Cadeia de fallback LLM

```
Gemini  →  Ollama (DeepSeek Coder local)
```

Se a confiança for baixa (`< 0.7`), a análise é marcada como `doubtful` e enviada para revisão humana. A correção do Tech Lead é reinserida no Qdrant como novo exemplo de calibração.

---

## Pré-requisitos

- Docker Desktop (com WSL2 / Hyper-V habilitado)
- Chave de API do [Google Gemini](https://aistudio.google.com/apikey) *(opcional — Ollama é o fallback)*

---

## Setup completo com Docker Compose

```bash
# Na raiz de artemis-ai:
cp .env.example .env
# Edite o .env com sua GEMINI_API_KEY

docker compose up -d
```

Isso sobe automaticamente:

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| `qdrant` | 6333 / 6334 | Banco vetorial — armazena Gold Set e embeddings |
| `perform-ai` | 8000 | FastAPI + pipeline Dual-LLM + RAG |
| `ollama` | 11434 | LLM local — baixa `deepseek-coder:6.7b` na primeira inicialização (~3.8 GB) |
| `perform-api` | 3000 | Backend NestJS |
| `perform-front` | 5123 | Frontend React/Vite |

> **Primeira inicialização:** o Ollama vai baixar o modelo `deepseek-coder:6.7b` (~3.8 GB). Após o download, o modelo fica persistido no volume `ollama_data` e as próximas inicializações são instantâneas.

---

## Variáveis de ambiente (.env)

```env
# Qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=

# LLM primário — Gemini
GEMINI_API_KEY=sua_chave_aqui
LLM_READER_MODEL=gemini-2.0-flash
LLM_SCORER_MODEL=gemini-2.0-pro-exp-03-25

# LLM fallback — Ollama local
OLLAMA_URL=http://ollama:11434
LLM_LOCAL_MODEL=deepseek-coder:6.7b

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Pipeline
CONFIDENCE_THRESHOLD=0.7
MAX_DIFF_LINES=3000

# NestJS callback
NESTJS_CALLBACK_URL=http://perform-api:3000
INTERNAL_API_KEY=perform_internal_key_2024
```

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Status do serviço, Qdrant, embedding model e Ollama |
| `POST` | `/api/v1/analyze-pr` | Analisa uma PR e retorna score de complexidade |
| `POST` | `/api/v1/feedback` | Envia correção humana para o Qdrant |
| `POST` | `/api/v1/gold-set` | Adiciona exemplo curado ao Gold Set |
| `GET` | `/api/v1/gold-set` | Lista todos os exemplos do Qdrant |
| `DELETE` | `/api/v1/gold-set/{id}` | Remove um exemplo |

Documentação interativa: `http://localhost:8000/docs`

---

## Exemplo de resposta

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
artemis-ai/
  app/
    main.py               # FastAPI app, CORS, lifespan
    config.py             # Configurações via .env (Gemini, Ollama, Qdrant)
    models/
      enums.py            # DifficultyLabel, ChangeType, etc.
      schemas.py          # Pydantic models (request/response)
    utils/
      diff_parser.py      # Parse de unified diffs do GitHub
      text_cleaner.py     # Remoção de ruído (imports, comentários, etc.)
    services/
      preprocessor.py     # Orquestra limpeza do diff
      embedding_service.py # sentence-transformers local (all-MiniLM-L6-v2)
      qdrant_service.py   # CRUD no banco vetorial
      llm_reader.py       # LLM 1 — resumo técnico (Gemini → Ollama fallback)
      llm_scorer.py       # LLM 2 — score final com RAG (Gemini → Ollama fallback)
      rag_pipeline.py     # Pipeline completo
    routers/
      analysis.py         # POST /analyze-pr
      feedback.py         # POST /feedback
      gold_set.py         # CRUD /gold-set
      health.py           # GET /health
  docker-compose.yml      # Qdrant + Ollama + FastAPI + NestJS + Frontend
  pyproject.toml
  Dockerfile
  .env.example
```

---

## Gold Set

O Gold Set são exemplos curados manualmente que servem como referência de calibração para o scorer. O projeto já possui **25 exemplos seed** cobrindo todos os níveis de dificuldade.

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

---

## Retry e tolerância a falhas

- **Tenacity AsyncRetrying** em ambos os LLMs: 3 tentativas, backoff exponencial (2s → 4s → 8s, máx. 30s)
- Se o Gemini esgotar quota (429) ou falhar após 3 tentativas → fallback automático para Ollama local
- Análises com confiança `< 0.7` ficam `doubtful` e aguardam revisão humana
