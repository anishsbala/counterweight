# Counterweight

[![CI](https://github.com/anishsbala/counterweight/actions/workflows/ci.yml/badge.svg)](https://github.com/anishsbala/counterweight/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Counterweight is a Dockerized claim-verification platform built with **Python, FastAPI, PostgreSQL, Redis, and Docker**. It ingests article text, extracts checkable claims, queues verification jobs across worker processes, ranks evidence from a curated source bank, assigns verdicts, and stores the full run in Postgres.

![Counterweight dashboard showing the verification form, source metrics, and queued run history](docs/assets/dashboard.png)

The core flow is:

1. **Parse article text** into clean sentences
2. **Extract checkable claims** with lightweight scoring heuristics
3. **Classify claim type and domain**
4. **Rank evidence** from a curated authority-weighted source bank
5. **Synthesize a verdict, confidence score, explanation, and reviewer note**
6. **Persist article, claims, evaluations, and evidence hits** to PostgreSQL
7. **Expose run history and source-bank views** through API routes and the demo UI

## Architecture

```mermaid
flowchart LR
    Browser[Dashboard] -->|REST| API[FastAPI]
    API -->|job state| Postgres[(PostgreSQL)]
    API -->|enqueue| Redis[(Redis)]
    Redis --> Worker1[Worker]
    Redis --> WorkerN[Scaled workers]
    Worker1 -->|results and status| Postgres
    WorkerN -->|results and status| Postgres
    Worker1 --> SourceBank[Curated source bank]
    WorkerN --> SourceBank
```

## Stack

- Python 3.11
- FastAPI
- PostgreSQL
- Docker / Docker Compose
- Plain HTML/CSS/JS frontend for demoing the pipeline

## Main features

- Better claim extraction than the original prototype
- Domain-aware retrieval across energy, climate, health, labor, economics, education, demographics, and technology
- Authority-weighted curated source bank with typed sources (`report`, `dataset`, `research`, `dashboard`, `policy`)
- Stronger verdict calibration with claim-level explanations and reviewer notes
- Full persistence for articles, claims, evaluations, and evidence hits
- Persistent PostgreSQL job state with Redis-backed worker dispatch
- Retryable Docker workers with queue recovery after API restarts
- Article history, source detail, domain breakdown, export route, benchmark route, and stats route
- Minimal but useful frontend so you can actually demo the project without sending people straight to `/docs`

## Data model

The database stores:

- `articles` — raw submission, dominant domain, overall verdict, summary, elapsed time
- `claims` — extracted claims with sentence index, normalized text, type, checkability score, key terms, and hedge flag
- `sources` — curated source bank with source type, tags, and authority score
- `claim_evaluations` — verdict, credibility score, confidence, explanation, reviewer note, evidence count
- `evaluation_evidence` — evidence ranking per claim, component scores, phrase hits, matched numbers, and stored snapshot

## Source bank

The source bank is intentionally curated and local to the repo. That keeps the project reproducible and easy to demo without depending on third-party APIs. The retriever uses domain alignment, keyword overlap, tag overlap, phrase overlap, source-type bonuses, and authority weighting.

Examples in the source bank:

- Energy: IEA, IRENA, EIA, NREL, Lazard, Our World in Data
- Climate: IPCC, NOAA, NASA, EPA
- Health: CDC, NIH, WHO, KFF
- Labor / economics: BLS, BEA, Federal Reserve, OECD, World Bank
- Education / demographics: NCES, Census Bureau, Urban Institute
- Technology: NIST, Semiconductor Industry Association, OECD AI, ITU, Stanford HAI

## Running the project

### Option 1: Docker (recommended)

From the project root:

```bash
docker compose up --build
```

Then open:

- Demo UI: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

The default Compose stack starts one worker. Scale it without changing application code:

```bash
docker compose up -d --scale worker=4
```

If you are reusing an older local volume from a previous Counterweight version, reset it once with:

```bash
docker compose down -v
```

That forces Postgres to rebuild the schema cleanly.

### Option 2: Local Python + local Postgres

1. Start PostgreSQL and Redis locally
2. Create a PostgreSQL database named `counterweight`
3. Set the environment variable:

#### PowerShell

```powershell
$env:DATABASE_URL="postgresql://counterweight:counterweight@localhost:5432/counterweight"
$env:REDIS_URL="redis://localhost:6379/0"
$env:DB_POOL_MAX_SIZE="10"
```

#### Bash

```bash
export DATABASE_URL="postgresql://counterweight:counterweight@localhost:5432/counterweight"
export REDIS_URL="redis://localhost:6379/0"
export DB_POOL_MAX_SIZE="10"
```

4. Install requirements:

```bash
pip install -r requirements.txt
```

5. Start the app:

```bash
uvicorn app.main:app --reload
```

The app auto-runs `sql/init.sql` and seeds the source bank on startup.

## Example requests

### In the browser

Open `http://localhost:8000/` and use the built-in form.

### In FastAPI docs

Open `http://localhost:8000/docs` and test `POST /verify`.

### In PowerShell

```powershell
$body = Get-Content .\scripts\sample_request.json -Raw
Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/verify" `
  -ContentType "application/json" `
  -Body $body
```

### In bash

```bash
curl -X POST "http://localhost:8000/verify"   -H "Content-Type: application/json"   -d @scripts/sample_request.json
```

## Useful endpoints

- `GET /health`
- `GET /benchmark`
- `POST /jobs`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/statuses`
- `GET /stats`
- `GET /domains`
- `GET /sources`
- `GET /sources/{slug}`
- `GET /articles`
- `GET /articles/{article_id}`
- `GET /articles/{article_id}/export`
- `POST /verify`

`POST /verify` remains available for synchronous development checks. The demo UI uses `POST /jobs`, and Docker workers perform the verification pipeline.

## Worker benchmark

```bash
python scripts/benchmark_workers.py --jobs 80
```

The benchmark preloads the same queued workload while workers are paused, then compares how quickly one worker and four workers drain Redis. Job-submission time is excluded so the result isolates worker throughput rather than serial API latency. Queue records remain durable, while duplicate article-history writes are disabled for the measurement.

It writes `benchmarks/latest.json`, which powers `GET /benchmark`. To enforce a target in CI or a controlled environment, add `--minimum-speedup 3.1`; the script will fail when the measured result is below that target. A threshold is an acceptance criterion, not a claimed result.

Only report the measured speedup from your machine or CI run.

## Current limitations

- Evidence comes from a curated local source bank rather than live web retrieval.
- Claim extraction, retrieval, and verdict calibration use deterministic heuristics rather than a trained fact-checking model.
- A verdict summarizes evidence alignment; it is not a guarantee that a claim is true or false.
- Authentication, authorization, and production abuse controls are outside the current local demo scope.
- Benchmark results depend on host resources, Docker configuration, database load, and workload shape.

## Running tests

```bash
pytest
```
