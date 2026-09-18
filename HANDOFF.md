# JanVaani — Handoff Notes for Team 3 (Backend & AWS Integration)

> **Written by:** Aditya (Person 1 — Ingestion & Source Verification)  
> **Branch:** `feature/ingestion-pipeline`  
> **Status:** All ingestion work complete, tested, and pushed. Ready for Team 3 to build on top.

---

## 1. What's already built (don't rebuild this)

Everything in this branch is Person 1's complete deliverable. The pipeline takes a government URL and writes a `CanonicalCircular` document into MongoDB — that's your starting point.

| File | What it does |
|------|-------------|
| `backend/lib/security.py` | URL allowlist, HTTPS enforcement, SSRF guard, `check_robots_txt()` |
| `backend/models/circular.py` | `CanonicalCircular` + `CandidateDocument` — **the shared data contract** |
| `backend/models/source.py` | `Source`, `CrawlPolicy`, `CrawlRun` models + PIB seed data |
| `backend/crawlers/base.py` | Abstract adapter, rate limiting, ETag caching, 403/429/WAF block handling |
| `backend/crawlers/pib.py` | Live PIB (pib.gov.in) listing + detail page parser |
| `backend/services/extraction_service.py` | HTML → text (BeautifulSoup), PDF → text (PyMuPDF), pasted-text path |
| `backend/services/provenance_service.py` | sha256 hashing, S3/local storage, duplicate detection, `save_circular()` |
| `backend/services/crawler_service.py` | Full crawl orchestration, `ingest_single_url()`, `ingest_pasted_text()` |
| `backend/workers/ingestion_worker.py` | FastAPI `BackgroundTask` wrappers |
| `backend/routers/ingestion.py` | `POST /url`, `POST /text`, `GET /{id}`, `POST /{id}/retry` |
| `backend/routers/sources.py` | Source CRUD, crawl trigger, crawl-run status, telemetry |
| `backend/lib/db.py` | Mongo indexes added for ingestion collections |
| `backend/server.py` | PIB source seeded to DB on startup |
| `backend/test_pipeline.py` | Acceptance test script — run this to verify the pipeline works |

---

## 2. How to get started locally

### Prerequisites
- Python 3.11+
- Docker (for MongoDB)
- No AWS credentials needed to start — storage falls back to local disk

### Steps

```bash
# 1. Clone and switch to the ingestion branch
git clone https://github.com/sanjanavenkatesh05/simple-sarkari.git
cd simple-sarkari
git checkout feature/ingestion-pipeline

# 2. Install Python dependencies
cd backend
pip install -r requirements.txt

# 3. Start MongoDB
docker run -d --name janvaani-mongo -p 27017:27017 mongo:7

# 4. Set up environment
cp .env.example .env
# Edit .env if needed — defaults work for local dev

# 5. Verify the ingestion pipeline works
python test_pipeline.py

# 6. Start the API server
uvicorn server:app --reload --port 8000
# Swagger docs → http://localhost:8000/docs
```

### Authentication for API calls
All `/api/admin/*` endpoints require:
```
Authorization: Bearer change-me-to-a-strong-secret
```
That default token is in `.env` as `REVIEWER_TOKEN`. Change it before any shared deployment.

---

## 3. The data contract — read this carefully

**MongoDB collection:** `circulars`  
**Document shape:** `CanonicalCircular` in `backend/models/circular.py`

This is the exact document shape that Person 1 writes and Team 3 reads. **Never rename or remove fields defined here** — only add new sub-objects (translation, review, audio).

### What Person 1 guarantees on every `extracted` document

```json
{
  "schema_version": "1.0",
  "id": "circular_<ulid>",
  "source": { "source_id": "pib", "source_name": "...", "source_url": "...", "official_document_url": "..." },
  "classification": { "government_level": "central", "department": "...", "document_type": "press_release", "language": "en-IN" },
  "identity": { "title_original": "..." },
  "content": { "original_text": "<non-empty>", "clean_text": "...", "sections": [] },
  "provenance": { "retrieved_at": "<ISO datetime>", "content_hash": "sha256:<hex>", ... },
  "processing": { "status": "extracted", "published": false, "translation_languages": [] }
}
```

### `processing.status` values — who owns what

| Status | Written by | Meaning |
|--------|-----------|---------|
| `extracted` | Person 1 | Ready for Team 3's pipeline |
| `manual_review_required` | Person 1 | Fetch was blocked (403/WAF/robots) — needs human attention |
| `translation_pending` | **Team 3** | |
| `under_review` | **Team 3** | |
| `approved` | **Team 3** | |
| `audio_ready` | **Team 3** | |
| `published` | **Team 3** | |

**Rule:** only process documents with `processing.status = "extracted"`. Skip `manual_review_required` — do not crash on them.

### Required fields (always present on `extracted` docs)
`id`, `source.source_id`, `source.source_name`, `source.source_url`,
`source.official_document_url`, `identity.title_original`,
`classification.government_level`, `classification.department`,
`classification.document_type`, `classification.language`,
`content.original_text`, `provenance.retrieved_at`,
`provenance.content_hash`, `processing.status`, `processing.published`

### Optional fields (may be `null` — never assume they're populated)
`dates.published_date`, `dates.effective_from`, `classification.state`,
`classification.category`, `identity.document_number`,
`identity.gazette_number`, `content.sections`, `attachments`,
`provenance.raw_html_s3_key`, `provenance.raw_pdf_s3_key`

---

## 4. Raw file storage

Raw HTML/PDF files are stored under the key:
```
raw/{circular_id}/v{version}/original.{html|pdf}
```

- **With AWS credentials configured:** stored in S3 bucket (`S3_BUCKET` env var)
- **Without AWS credentials:** stored on local disk at `backend/data/` under the same path structure

The `provenance.raw_html_s3_key` and `provenance.raw_pdf_s3_key` fields on the document hold this key. To retrieve a file:

```python
from services.provenance_service import retrieve_raw
raw_bytes = await retrieve_raw("raw/circular_abc123/v1/original.html")
```

`retrieve_raw()` tries S3 first, falls back to local disk automatically.

---

## 5. Key dependencies — what's in requirements.txt

```
fastapi==0.115.12       # API framework
uvicorn[standard]       # ASGI server
pydantic==2.11.3        # Data models (v2 — use model_dump(), not dict())
pydantic-settings       # Settings from .env
motor==3.7.1            # Async MongoDB driver
pymongo==4.12.1         # MongoDB (motor dependency)
httpx==0.28.1           # Async HTTP client (used by crawler)
beautifulsoup4==4.13.4  # HTML parsing
lxml==5.4.0             # HTML parser backend for BeautifulSoup
pymupdf==1.25.5         # PDF text extraction (import as `fitz`)
boto3==1.38.34          # AWS SDK (S3, Bedrock, Polly)
python-ulid==3.0.0      # ULID generation for circular IDs
structlog==25.4.0       # Structured logging
python-jose             # JWT tokens
passlib[bcrypt]         # Password hashing
```

### Pydantic v2 gotchas (important!)
- Use `model.model_dump(mode="json")` — not `model.dict()`
- Use `model.model_validate(data)` — not `Model(**data)` on raw dicts from Mongo
- `Field(default_factory=...)` still works the same way
- Validators use `@field_validator` decorator now

### Motor (async MongoDB) gotchas
- All DB calls must be `await`ed
- `find()` returns a cursor — iterate with `async for doc in cursor`
- Documents from Mongo include `_id` field — strip it before passing to Pydantic: `doc.pop("_id", None)`
- The DB is initialized in `server.py` lifespan — use `get_db()` as a FastAPI dependency

---

## 6. MongoDB collections

| Collection | Owner | Purpose |
|-----------|-------|---------|
| `circulars` | Shared | Main `CanonicalCircular` documents |
| `sources` | Person 1 | Source registry (PIB etc.) |
| `crawl_runs` | Person 1 | Crawl run telemetry |
| `ingestion_jobs` | Person 1 | Manual ingestion job tracking |
| `translations` | **Team 3** | Translation records |
| `reviews` | **Team 3** | Human review records |
| `audio_assets` | **Team 3** | Generated audio metadata |
| `jobs` | **Team 3** | Background job queue |
| `audit_events` | Shared | Audit trail (both sides write here) |

---

## 7. What Team 3 needs to build next

Based on CONTEXT.md §3.2, the immediate next steps are:

### 7.1 AI simplification (`services/ai_service.py`)
- Query MongoDB for docs with `processing.status = "extracted"`
- Call Bedrock (Claude) with `content.original_text` to produce a simplified English version
- Store result back on the circular document
- Update `processing.status = "translation_pending"`

```python
# Bedrock client is already wired up in lib/aws.py
from lib.aws import get_bedrock_client
```

### 7.2 Translation (`services/translation_service.py`)
- Translate the simplified text into regional languages
- Write to the `translations` collection
- Update `processing.translation_languages` on the circular

### 7.3 Review workflow (`routers/review.py`)
- Endpoints for human reviewers to approve/reject translated content
- Move status from `under_review` → `approved` or back

### 7.4 Audio generation (`services/audio_service.py`)
- Call Polly with approved translation text
- Upload audio to S3 under `audio/{circular_id}/{language}.mp3`
- Update `processing.status = "audio_ready"`

### 7.5 Public API (`routers/public.py`)
- Serve approved + published circulars to citizens
- Search, filter by department/language/date
- Return audio URLs via signed S3 links

---

## 8. AWS environment variables needed

```env
AWS_REGION=ap-south-1
S3_BUCKET=janvaani-dev          # bucket for raw files + audio
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
POLLY_REGION=ap-south-1
```

AWS credentials should be set via environment variables or IAM role:
```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

The S3 client (`lib/aws.py`) is already wired up — just set the env vars and `upload_to_s3()` / `download_from_s3()` will work.

---

## 9. Branching strategy

```
main                        ← integration branch (always demo-able)
feature/ingestion-pipeline  ← Person 1's branch (merge this into main first)
team3-backend               ← Team 3's branch (rebase onto main after Person 1 merges)
```

**Recommended merge order:**
1. Merge `feature/ingestion-pipeline` → `main` (Person 1's PR)
2. `git rebase main` on `team3-backend` to pick up the shared models
3. Never force-push `main`

---

## 10. Quick API reference

All admin endpoints require `Authorization: Bearer <REVIEWER_TOKEN>`.

```
# Ingest a URL
POST /api/admin/ingestions/url
Body: { "url": "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=123456", "source_id": "pib" }

# Ingest pasted text
POST /api/admin/ingestions/text
Body: { "title": "...", "publisher": "Ministry of...", "source_url": "...", "text": "..." }

# Poll ingestion job status
GET /api/admin/ingestions/{job_id}

# Manual retry
POST /api/admin/ingestions/{job_id}/retry

# Trigger a full crawl run
POST /api/admin/sources/pib/crawl
Body: { "max_pages": 5, "max_documents": 20 }

# Poll crawl run status
GET /api/admin/crawl-runs/{run_id}

# Source telemetry
GET /api/admin/sources/pib/telemetry
```

Full interactive docs at: `http://localhost:8000/docs`

---

## 11. Known issues / notes

- **PIB 403 on some networks:** PIB's Akamai WAF blocks requests from some IPs. The pipeline handles this correctly (`manual_review_required`) — it's not a code bug. Works fine from a clean server IP. The User-Agent is set to a Mozilla-compatible string which helps on most networks.
- **No AWS needed for local testing:** `store_raw()` and `retrieve_raw()` fall back to `backend/data/` on disk automatically if S3 is unavailable.
- **`python-ulid` import:** if `ulid.new()` doesn't exist on your version, the code falls back to `uuid.uuid4()` — both produce valid unique IDs.
- **Pydantic v2:** the codebase uses Pydantic v2 throughout. Do not downgrade to v1 — it will break model validation.
- **`content_hash` conflict with old index:** `lib/db.py` has an old flat index `content_hash` (unique) from the original scaffold. The new index is on `provenance.content_hash`. If you see a duplicate key error on startup, drop the old `content_hash` index from the `circulars` collection manually.

---

*Last updated by Aditya — branch `feature/ingestion-pipeline` @ commit `6669726`*
