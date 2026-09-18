# JanVaani — Government Circulars for Everyone

> Simplify, translate, and narrate Indian government circulars so every citizen can understand them.

## Architecture

```
Government Sources → Crawlers → Extraction → Bedrock AI → Human Review → Polly Audio → Public Catalogue
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB (local or Atlas)
- AWS credentials with access to S3, Bedrock, and Polly

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env           # Edit with your credentials
uvicorn server:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` and proxies `/api/*` requests to the backend at `http://localhost:8000`.

## Project Structure

```
simple-sarkari-/
├── backend/
│   ├── server.py              # FastAPI entry point
│   ├── config.py              # Pydantic settings
│   ├── models/                # Pydantic data models
│   │   ├── source.py          # Source registry
│   │   ├── circular.py        # Government circulars
│   │   ├── translation.py     # AI translations
│   │   ├── review.py          # Human review workflow
│   │   ├── job.py             # Background jobs
│   │   └── audio.py           # Audio assets
│   ├── routers/               # API route handlers
│   │   ├── system.py          # Health checks
│   │   ├── public.py          # Citizen-facing catalogue
│   │   ├── ingestion.py       # Document ingestion (admin)
│   │   ├── sources.py         # Source management (admin)
│   │   ├── processing.py      # Job monitoring (admin)
│   │   ├── review.py          # Review workflow (admin)
│   │   └── crawler.py         # Crawler management (admin)
│   ├── services/              # Business logic
│   │   ├── crawler_service.py
│   │   ├── extraction_service.py
│   │   ├── ai_service.py
│   │   ├── translation_service.py
│   │   ├── audio_service.py
│   │   ├── search_service.py
│   │   └── provenance_service.py
│   ├── crawlers/              # Source-specific adapters
│   │   ├── base.py            # Abstract base adapter
│   │   ├── pib.py             # Press Information Bureau
│   │   ├── dopt.py            # Dept. of Personnel & Training
│   │   ├── egazette.py
│   │   ├── doe.py
│   │   ├── india_gov.py
│   │   ├── karnataka_egazette.py
│   │   ├── karnataka_dpar.py
│   │   ├── karnataka_finance.py
│   │   └── karnataka_itbt.py
│   ├── workers/               # Background task handlers
│   │   ├── ingestion_worker.py
│   │   ├── extraction_worker.py
│   │   ├── translation_worker.py
│   │   └── audio_worker.py
│   └── lib/                   # Shared utilities
│       ├── db.py              # MongoDB async client
│       ├── aws.py             # S3 / Bedrock / Polly clients
│       ├── dates.py           # Indian date parsing
│       └── security.py        # URL validation, auth
├── frontend/
│   ├── src/
│   │   ├── components/        # Navbar, Layout
│   │   ├── pages/             # HomePage, CircularPage, Admin, Reviews, Ingest
│   │   ├── hooks/             # TanStack Query hooks
│   │   ├── lib/               # API client
│   │   └── types/             # TypeScript types
│   └── vite.config.ts         # Tailwind v4 + API proxy
└── .gitignore
```

## API Endpoints

### Public (no auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness check |
| GET | `/api/health/ready` | Readiness check |
| GET | `/api/circulars` | Search published circulars |
| GET | `/api/circulars/{id}` | Get circular detail |
| GET | `/api/circulars/{id}/translations/{lang}` | Get translation |
| GET | `/api/circulars/{id}/audio/{lang}` | Get audio URL |
| GET | `/api/catalogue/filters` | Available search filters |

### Admin (Bearer token required)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/ingestions/url` | Ingest from URL |
| POST | `/api/admin/ingestions/text` | Ingest pasted text |
| GET | `/api/admin/ingestions/{id}` | Ingestion status |
| POST | `/api/admin/ingestions/{id}/retry` | Retry ingestion |
| GET | `/api/admin/sources` | List sources |
| GET | `/api/admin/sources/{id}` | Get source |
| POST | `/api/admin/sources` | Add source |
| PATCH | `/api/admin/sources/{id}` | Update source |
| POST | `/api/admin/sources/{id}/crawl` | Trigger crawler |
| GET | `/api/admin/crawl-runs/{id}` | Crawl run status |
| GET | `/api/admin/sources/{id}/telemetry` | Source telemetry |
| GET | `/api/admin/jobs` | List jobs |
| GET | `/api/admin/jobs/{id}` | Get job |
| POST | `/api/admin/jobs/{id}/retry` | Retry job |
| POST | `/api/admin/jobs/{id}/cancel` | Cancel job |
| GET | `/api/admin/reviews` | Review queue |
| GET | `/api/admin/reviews/{id}` | Get review |
| PATCH | `/api/admin/reviews/{id}` | Save edits |
| POST | `/api/admin/reviews/{id}/redraft` | Request AI redraft |
| POST | `/api/admin/reviews/{id}/approve` | Approve (publish) |
| POST | `/api/admin/reviews/{id}/reject` | Reject |
| POST | `/api/admin/reviews/{id}/flag` | Flag for audit |

## Tech Stack

**Frontend:** React 19 · TypeScript · Vite · Tailwind CSS v4 · TanStack Query · React Router · Sonner

**Backend:** FastAPI · Pydantic v2 · Motor / MongoDB · httpx · BeautifulSoup · PyMuPDF · boto3

**AWS:** S3 · Bedrock · Polly · Secrets Manager · IAM · CloudWatch