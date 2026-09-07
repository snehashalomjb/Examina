# Examina — AI-Based Examination Platform

A full-stack examination platform for two audiences on one engine: academic institutions
running subject-based exams, and companies running sectioned recruitment assessments. One
question bank, one paper generator, one grading pipeline, one candidate runner — the exam
type changes what an examiner configures, not how the platform works underneath.

FastAPI + PostgreSQL on the backend, Next.js + TypeScript on the frontend, JWT auth with
per-role access control, in-browser AI proctoring, and a pluggable objective/subjective
grading pipeline.

## What it does

**Question bank.** One bank, nine question types — single/multi-select MCQ, true/false,
fill-in-the-blank, numerical (with tolerance), short/long answer, handwritten image
upload, passage/case-study with child questions, and coding. Each question carries a
category, topic, difficulty and status, with type-specific configuration (an answer key,
a coding problem statement, a passage's text) validated against a strict schema per type
— an examiner's typo in a field name is rejected at save time, not silently ignored at
grading time.

**Two exam modes, one engine.** An exam is `academic` or `corporate`; both are built from
ordered **sections**, each with its own question-selection rules, and both run through the
same session lifecycle, timer, autosave and grading pipeline. An academic exam typically
has one implicit section; a corporate exam can chain Aptitude → Reasoning → Verbal →
Technical → Coding, each independently configured.

**Deterministic papers.** A candidate's paper is generated once, seeded from the exam id,
candidate id and a per-exam salt, then frozen into the session — a server restart or a
retried request can never reshuffle a live exam. Re-attempts (when an exam allows more
than one) get a distinct seed and a genuinely different paper.

**Server-authoritative timing.** The client's clock is never trusted: `expires_at` is
computed and stored server-side at session start, every request re-checks it, and an
APScheduler job auto-submits any session whose time has run out even if the candidate's
tab is closed.

**AI proctoring.** MediaPipe's face landmarker runs client-side (WASM/WebGL, no per-session
server cost) to watch face presence, multiple faces, and head-pose-based gaze; the browser
also reports tab switches, window blur, fullscreen exit and clipboard use. Every signal is
weighted and persisted as a `proctor_events` row and rolled into a 0–100 suspicion score
recomputed **from the stored events**, never from a client-supplied number — a batched HTTP
endpoint and a WebSocket channel both feed the same scoring path, so the transport can
degrade without losing signal.

**Grading.** Objective and typed-response types (MCQ, true/false, fill-blank, numerical)
score automatically at submission. Short/long answer, image uploads and coding go to a
review queue with a pluggable first-pass grader — an offline deterministic stub by
default, or a real model (Claude or GPT-4o) if a provider key is configured — with its
score, justification and confidence shown to the examiner as a suggestion, never as a
final grade. Handwritten scans get an OCR pass (Tesseract) for a searchable transcript
alongside the image.

**Corporate recruitment.** A ranking table (score, section breakdown, accuracy, time
taken) and manual shortlisting — the platform ranks and surfaces candidates; an examiner
decides. Bulk question import from an existing PDF, and AI-assisted question generation
that lands in a review queue and is never auto-published.

**Analytics.** Per-exam aggregates (score distribution, section performance, topic and
difficulty breakdowns) for examiners, a live operations view for in-progress sessions, and
a personal accuracy/trend view for candidates on their own published results.

## Stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + SQLAlchemy 2.0 (sync) | Simple code and tests; endpoints run in a threadpool |
| Database | PostgreSQL 16 | Native enums, JSONB, array columns |
| Auth | JWT (python-jose) + argon2id | Short-lived exam-session tokens bound to `(session, exam, candidate)` |
| Object storage | MinIO (S3-compatible) | Snapshots and scans out of Postgres; presigned URLs for review |
| Frontend | Next.js (App Router) + TypeScript + Tailwind | — |
| Vision | MediaPipe Tasks-Vision, in-browser | Proctoring cost doesn't scale with concurrent sessions |
| Migrations | Alembic | — |

## Getting started

**Prerequisites:** Docker Desktop, Python 3.12+, Node 20+, [uv](https://docs.astral.sh/uv/).
Tesseract OCR is optional — only handwritten-answer OCR degrades without it.

```bash
# 1. Infrastructure
docker compose up -d db db_test minio

# 2. Environment
cp .env.example .env

# 3. Backend
cd backend
uv venv --python 3.12
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
uv pip install -e ".[dev]"
uv run alembic upgrade head
uv run python -m app.seed          # sample subjects, questions and exams
uv run uvicorn app.main:app --reload --port 8000

# 4. Frontend
cd ../frontend
npm install
npm run dev
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API (Swagger) | http://127.0.0.1:8000/docs |
| MinIO console | http://localhost:9001 (`minioadmin` / `minioadmin`) |
| Postgres | `localhost:5433`, db `examdb`, user/pass `exam`/`exam` |

Seeded demo accounts (password `Passw0rd!` unless noted):

| Role | Email |
|---|---|
| Admin | `admin@exam.edu` (`Admin@12345`) |
| Examiner | `examiner@exam.edu` |
| Candidate | `candidate1@exam.edu` |

## Testing

```bash
cd backend && uv run pytest        # unit + API tests, isolated test database
cd frontend && npx tsc --noEmit && npm run lint
```

## Layout

```
backend/app/
  api/v1/       REST + WebSocket routes — exams, sections, questions, exam_sessions,
                proctor, grading, results, analytics, recruitment, ai_questions
  db/models/    SQLAlchemy models: users, question bank, exams/sections, sessions,
                answers, results, proctor events, AI drafts, recruitment
  services/     paper generator, exam engine, auto-evaluator, suspicion scoring,
                OCR, PDF import/export, pluggable grading (stub / Claude / OpenAI)
  schemas/      Pydantic request/response models
  tests/        pytest suite

frontend/src/
  app/          Next.js App Router — dashboards per role, exam runner, results
  components/   UI primitives, live operations dashboard, proctoring preview
  lib/          API client, auth context, the MediaPipe proctoring engine, types
```

See [WORKBENCH.md](WORKBENCH.md) for architectural decisions, known gaps and open threads.
