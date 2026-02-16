# Question Cluster API

**Automatic FAQ generation from repeated Slack questions using semantic similarity clustering.**

> 📚 Portfolio project demonstrating knowledge management automation, embedding-based clustering, and cross-platform integration (Slack → API → Notion).

## Problem Statement

In active Slack communities, the same questions get asked repeatedly by different people. This creates:
- **Information fragmentation** - answers scattered across threads
- **Duplicated effort** - team members answering the same questions
- **Poor discoverability** - no central FAQ or knowledge base

## Solution

An automated system that:
1. **Monitors** incoming Slack messages
2. **Clusters** semantically similar questions using embeddings
3. **Triggers** FAQ draft creation when a question is asked 3+ times
4. **Routes** drafts to Notion for review and publication

## Architecture

```
┌─────────────────┐
│  Slack Channel  │
│   (Monitored)   │
└────────┬────────┘
         │ message event
         ▼
┌─────────────────────────────────────────────────┐
│   n8n Workflow  (Railway)                       │
│  ┌───────────┐                                  │
│  │ Trigger   │  ← Slack event subscriptions     │
│  └─────┬─────┘                                  │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ IF (Regex)    │  ← Basic filter: has "?" or  │
│  └─────┬─────────┘    question words            │
│        │                                         │
│  ┌─────▼─────────────┐                          │
│  │ LLM Filter        │  ← Anthropic Claude:     │
│  │ (Anthropic)       │    "Is this a genuine    │
│  └─────┬─────────────┘    question?"            │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ IF (yes?)     │  ← LLM response check        │
│  └─────┬─────────┘                              │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ HTTP POST     │  ← /check endpoint           │
│  └─────┬─────────┘                              │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ IF (≥3 && not │  ← Cluster threshold +       │
│  │  drafted?)    │    draft prevention          │
│  └─────┬─────────┘                              │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ LLM Draft FAQ │  ← Anthropic Claude:         │
│  │ (Anthropic)   │    generate FAQ entry        │
│  └─────┬─────────┘                              │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ Code (parse)  │  ← Extract Question/Answer   │
│  └─────┬─────────┘                              │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ Notion        │  ← Create page in FAQ DB     │
│  └─────┬─────────┘                              │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ HTTP POST     │  ← /mark-drafted endpoint    │
│  └─────┬─────────┘                              │
│        │                                         │
│  ┌─────▼─────────┐                              │
│  │ Slack Message │  ← Notify docs channel       │
│  └───────────────┘                              │
└─────────────────────────────────────────────────┘
         │
         │ POST /check
         ▼
┌─────────────────┐
│  Python API     │  (Railway)
│  FastAPI        │
│  ┌───────────┐  │
│  │ Embedding │  │ ← OpenAI text-embedding-3-small
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ Similarity│  │ ← Cosine similarity (threshold: 0.70)
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ Cluster   │  │ ← Assign to cluster or create new
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ SQLite    │  │ ← Persistent storage (Railway volume)
│  └───────────┘  │
└─────────────────┘
```

## Key Design Decisions

### 1. Two-Stage Question Filtering
- **Stage 1 (Regex):** Fast pattern matching for obvious questions (`?` or question words like "how", "what", "where")
- **Stage 2 (LLM - Anthropic Claude):** Semantic analysis to filter out:
  - Rhetorical questions ("Why is this so hard???")
  - Greetings ("How are you?")
  - Time-sensitive queries ("What time is the meeting?")
  - Vague requests ("Can someone help me?")
- **Why:** Reduces API costs by filtering 90% of non-questions with cheap regex before using LLM
- **Trade-off:** Adds ~1-2 seconds latency per message, but ensures only genuine FAQ-worthy questions are clustered

### 2. LLM Choice: Anthropic Claude vs OpenAI GPT
- **Why Claude:** More reliable at following strict formatting instructions (Question: / Answer: structure)
- **Experience:** OpenAI models (GPT-4o-mini, GPT-3.5-turbo) produced inconsistent or empty outputs with structured prompts
- **Use cases:** Claude handles both question filtering and FAQ draft generation

### 3. Embedding Model: OpenAI `text-embedding-3-small`
- **Why:** Good balance of performance (1536 dimensions) and cost ($0.02 per 1M tokens)
- **Alternatives considered:** `text-embedding-3-large` (higher accuracy but 3x cost), Sentence-BERT (self-hosted but more complex)

### 4. Similarity Metric: Cosine Similarity
- **Why:** Standard for embedding comparison, robust to question length variations
- **Threshold:** 0.70 (empirically tuned, see [TUNING_LOG.md](TUNING_LOG.md))
- **Rationale:** Paraphrased questions score 0.70-0.75, different topics score <0.55

### 5. Clustering Logic: Incremental
- **Why:** Real-time clustering as questions arrive (vs. batch processing)
- **Trade-off:** Simpler to implement, but doesn't handle cluster merging or splitting

### 6. Storage: SQLite on Railway Volume
- **Why:** Simple, serverless-friendly, sufficient for moderate scale (<10K questions)
- **Limitations:** No built-in vector search (could migrate to PostgreSQL with pgvector for larger scale)

### 7. FAQ Trigger Threshold: 3 occurrences
- **Why:** Balances noise reduction (not every question) with timeliness (catches real patterns quickly)
- **Draft Prevention:** After first FAQ is created, cluster is marked `faq_drafted: true` to prevent duplicates
- **Configurable:** Can be adjusted based on channel activity

## API Endpoints

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| `GET` | `/` | Service info | ✅ Live |
| `GET` | `/health` | Health check | ✅ Live |
| `POST` | `/check` | Cluster a new question | ✅ Live |
| `GET` | `/clusters` | List all clusters | ✅ Live |
| `POST` | `/clusters/{id}/mark-drafted` | Mark FAQ as drafted | ✅ Live |
| `POST` | `/reset` | Clear database (testing only) | ⚠️ Dev only |
| `POST` | `/debug` | Inspect similarity scores | ⚠️ Dev only |

**Production URL:** `https://question-cluster-api-production.up.railway.app`

### Example: Check a Question
```bash
curl -X POST https://question-cluster-api-production.up.railway.app/check \
  -H "Content-Type: application/json" \
  -d '{
    "text": "How do I reset my password?",
    "source_channel": "C12345",
    "source_user": "U67890"
  }'
```

Response:
```json
{
  "status": "matched",
  "cluster_id": 6,
  "cluster_count": 3,
  "similar_questions": [
    "How do I reset my password?",
    "Where do I change my password?",
    "I forgot my password, how do I get a new one?"
  ]
}
```

## Deployment

### Stack
- **API:** FastAPI (Python 3.11)
- **Hosting:** Railway (Docker)
- **Database:** SQLite (volume-mounted at `/data`)
- **Workflow:** n8n (also on Railway)
- **LLM:** Anthropic Claude (question filtering + FAQ drafting)
- **Embeddings:** OpenAI text-embedding-3-small

### Environment Variables

**Python API Service:**
| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings |
| `DB_PATH` | Database file path (default: `/data/questions.db`) |
| `PORT` | Auto-assigned by Railway |

**n8n Service:**
| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude LLM nodes |
| `SLACK_BOT_TOKEN` | Slack bot token for event subscriptions |
| `NOTION_API_KEY` | Notion integration token |

### Local Development
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="sk-..."
export DB_PATH="./questions.db"

# Run server
uvicorn main:app --reload --port 8000
```

## Limitations & Future Work

### Current Limitations
1. **No cluster merging** - If similar questions are added before threshold is reached, they may form separate clusters
2. **No multi-language support** - Embeddings are English-optimized
3. **No user deduplication** - Same exact question from same user can inflate cluster count
4. **Partial draft prevention** - `/mark-drafted` endpoint exists but API doesn't return `faq_drafted` status yet
5. **No auth** - `/reset` and `/debug` endpoints are public (dev only)
6. **LLM filtering adds latency** - ~1-2 seconds per message for Claude API call

### Potential Enhancements
- [ ] Complete draft prevention loop (return `faq_drafted` in `/check` response, check in n8n IF node)
- [ ] Add user deduplication (don't count same user asking same question twice)
- [ ] Implement cluster merging (periodic job to merge high-similarity clusters)
- [ ] Add authentication for admin endpoints
- [ ] Migrate to PostgreSQL with pgvector for better vector search
- [ ] Add analytics dashboard (cluster trends, top questions, response times)
- [ ] Support multi-language questions (use multilingual embedding models)
- [ ] Add feedback loop (mark drafted FAQs as "helpful" or "not helpful")
- [ ] Cache LLM filter results to reduce API costs for repeated message patterns
- [ ] Add confidence scores to LLM filter (not just yes/no, but 0-100% confidence)

## Testing

See [TUNING_LOG.md](TUNING_LOG.md) for threshold calibration methodology.

### Run Tests Locally
```bash
# Reset database
curl -X POST http://localhost:8000/reset

# Add questions and verify clustering
curl -X POST http://localhost:8000/check \
  -H "Content-Type: application/json" \
  -d '{"text": "How do I reset my password?"}'

# Check similarity scores
curl -X POST http://localhost:8000/debug \
  -H "Content-Type: application/json" \
  -d '{"text": "Where do I change my password?"}'
```

## License

MIT License - see [LICENSE](LICENSE) for details.
