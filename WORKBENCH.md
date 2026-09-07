# Workbench

Running log of decisions, discoveries and open threads. The README says what the platform
*is*; this file says *why it is that way* and what is left.

---

## Decisions

| # | Decision | Why | Alternative rejected |
|---|---|---|---|
| 1 | Full 4-module skeleton first, depth after | Integration risk gets paid down in week 1 instead of week 4 | Weeks 1–2 only |
| 2 | PostgreSQL 16 in Docker Compose, host port **5433** | Native enums, JSONB and array columns; 5433 avoids colliding with a host Postgres | SQLite dev (dialect drift) |
| 3 | **Sync** SQLAlchemy 2.0 + psycopg 3 | Simpler code and tests; FastAPI runs endpoints in a threadpool | Async + asyncpg |
| 4 | Vision **in the browser** (MediaPipe) | Proctoring cost does not scale with concurrency | Server-side OpenCV/mediapipe |
| 5 | **WebSocket first, batched HTTP POST as fallback** (~10 s) | Revised. The socket delivers the verdict on the server's schedule, not the client's next poll; the POST path stays for proxies that will not carry a socket and for the unload flush, and both run the same ingest code | Either transport alone |
| 6 | **MinIO** for snapshots and answer scans | S3-compatible → real S3 later is an env-var change; presigned URLs for review | Local filesystem |
| 7 | Grader is **pluggable, `stub` active** | Requested: no model for now. Whole pipeline is exercisable and testable offline | Hard-wiring a provider |
| 8 | `argon2-cffi` directly, not `passlib` | passlib is unmaintained and trips the `crypt` deprecation on 3.12+; argon2id has no bcrypt 72-byte truncation trap | passlib[bcrypt] |
| 9 | Answer rows **pre-created at session start** | Autosave becomes a plain update; the grading queue is one table scan with no missing-row cases | Insert on first answer |
| 10 | Paper frozen into `exam_sessions.question_order` | A server restart mid-exam cannot reshuffle a live paper | Regenerate from seed each request |
| 11 | Light theme only | Exam halls are bright and screens get invigilated over the shoulder | Theme toggle |
| 12 | Low-poly geometry is **hand-placed, not random** | Deterministic and balanced; identical on every render | Runtime-generated mesh |
| 13 | Word ceilings are enforced at **save**, floors only **reported** at submit | Autosave fires mid-sentence: rejecting a half-written answer for being under the minimum throws away work at word three of a hundred | Enforcing both at save |
| 14 | OCR runs **after** the upload response, in a background task | A page of handwriting takes seconds and the candidate is mid-exam; the examiner only needs the text by the time the exam closes | Blocking the upload on OCR |
| 15 | OCR output is **advisory**, never scored against | Handwriting recognition is not reliable enough to derive a mark from, and the examiner is reading the image anyway | Feeding OCR text to the grader as the answer |
| 16 | Socket auth in `Sec-WebSocket-Protocol`, not the query string | The browser WebSocket API cannot set an `Authorization` header, and a token in a URL is printed into every proxy and access log — the same reasoning that ruled out `sendBeacon` | `?token=` |

## Discoveries (things that bit, and the fix)

**`.local` email domains are rejected.** Every login returned `422 … "The part after the
@-sign is a special-use or reserved name"`. `email-validator` (behind Pydantic's
`EmailStr`) refuses reserved TLDs — `.local`, `.test`, `.example`, `.invalid`. Moved all
demo/test accounts to `@exam.edu` / `@test.edu`.

**`from __future__ import annotations` breaks FastAPI dependency factories.** Every
question-bank route 422'd with `"user: Field required"`. With stringified annotations,
FastAPI cannot resolve a *closure-local* name inside `Annotated[User, Depends(role_gate)]`,
so it treated `user` as a required query parameter. Fix: declare those dependencies as
default values — `def _dependency(user: User = Depends(role_gate))` — which are evaluated
at definition time. Noted in a comment at `backend/app/core/deps.py` so it does not get
"tidied" back.

**The test `get_db` override must not roll back.** Mirroring the real dependency's
`except: rollback()` meant that any request returning 403 rolled back the *outer* test
transaction, destroying fixtures created before the request — a test would create an admin,
get a 403 from a deliberate access check, and then fail to log that admin in. The override
now only yields and flushes; the fixture owns the transaction.

**Greedy rule ordering starved specific rules.** A rule pair of `mcq/any × 5` then
`mcq/easy × 3` could fail against a pool with 4 easy MCQs, because the catch-all ate them
first. Rules are now ordered most-specific-first, and `check_pool_satisfies_rules` walks
them with the same consumption the generator uses, so "publishable" means "every
candidate's paper can actually be built".

**`sendBeacon` cannot carry auth headers.** The unload flush targets authenticated
endpoints. Putting tokens in a query string would leak them into access logs, so the flush
uses `fetch(..., { keepalive: true })` instead, which survives unload *and* sends headers.

**React 19's `react-hooks/set-state-in-effect` flags mount-time fetching.** The rule traces
into the called loader, so the ordinary "fetch on mount, store in state" pattern errors.
Two genuine violations were fixed properly (a synchronous `setLoading(false)` in an effect
body; derived subject state that is now computed during render). The rule is set to `warn`
in `eslint.config.mjs` with the reasoning inline, so real mistakes still surface.

**A WebSocket route needs `Depends`, not `SessionLocal()`.** The socket handler first
opened its own session directly, which made it untestable: the test suite's `get_db`
override hands out a session inside a rolled-back transaction, and a handler that bypasses
the dependency talks to the *dev* database instead, seeing none of the fixtures. FastAPI
does support `Depends` on websocket endpoints, so the handler takes `db: Session =
Depends(get_db)` like every other route and the override applies. It commits per batch,
which inside a test commits the nested transaction and leaves the fixture's outer one to
roll back — the standard join-an-external-transaction pattern.

**`uv pip install` into the venv silently dropped `apscheduler`.** Adding Pillow and
pytesseract left the environment without a package nothing had asked to remove; every
DB-backed test then failed at `conftest` import. Reinstalling it fixed it. Worth knowing
before blaming a code change for a wall of collection errors.

**The word counter has to be written twice, identically.** Python's `[^\W_]+` under
`re.UNICODE` and JavaScript's `\w` are not the same character class — JS `\w` is ASCII
only. The browser counter uses `[\p{L}\p{N}\p{M}]` with the `u` flag to match Python's
behaviour, and every save echoes the server's count back so any residual drift is
corrected rather than argued about. A counter that says 249 while the API refuses at 251
is worse than no counter.

## Verified end to end

- `pytest` — **204 passed** (was 142 before word limits, OCR/thumbnails and the socket).
- `ruff check app` — clean. `tsc --noEmit` — clean.
- `eslint src` — 1 error, **pre-existing and unrelated**: `Math.random()` inside the
  `useMemo` in `candidate/welcome/page.tsx` now trips React 19's impure-render rule.
- `next build` — 25 routes compiled.
- OCR tests exercise the real Tesseract binary (5.5 locally) by rendering text with PIL and
  reading it back; they skip rather than fail where it is not installed.
- Live API smoke test against seeded data: every endpoint the UI calls returns 200; the
  pending examiner gets `403 "Your account is awaiting administrator approval."`; calling
  `preview-paper` twice for one candidate returns **identical** papers (10 questions).

## Open threads

- [ ] Background grading uses FastAPI `BackgroundTasks`. Under real load move it to a
      worker queue — `grade_pending_answers(db, session_id)` is already a plain function.
- [ ] No concurrency load test yet. The plan called for ~50 simultaneous sessions to tune
      `pool_size` / `max_overflow` (currently 20/30).
- [ ] No frontend test suite. The exam runner's timer/autosave/heartbeat interplay is the
      part most worth covering.
- [ ] Bulk question import exists in the API (`POST /questions/bulk`) but has no UI.
- [ ] Exam editing after publish is blocked once anyone has started — no "clone this exam"
      escape hatch yet.
- [ ] `devtools_open` is in the event enum and weighted, but nothing emits it client-side;
      reliable detection is hostile to do well and easy to do badly.
- [ ] The `openai` and `claude` graders are wired but have never run against a live API —
      only the stub is exercised by tests. The response-parsing shape is the risk.
- [ ] No load test of the proctor socket. One long-lived connection per sitting holds a DB
      session for the duration; at ~50 concurrent sittings that wants checking against
      `pool_size`/`max_overflow` before it wants tuning.
- [ ] OCR quality on real handwriting is unmeasured. Tesseract on a phone photo of cursive
      is often close to useless; the panel is honest about that, but if examiners find it
      noise rather than help, a vision-model transcription is the upgrade path.
- [ ] Results are per-session. No cohort analytics (distribution, per-question difficulty
      from actual responses) yet — the data is all there for it.

## Operations

```bash
# infrastructure
docker compose up -d db db_test minio
docker compose ps
docker compose exec db psql -U exam -d examdb

# backend
cd backend
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m alembic revision --autogenerate -m "message"
.venv/Scripts/python -m app.seed
.venv/Scripts/python -m pytest
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm run dev
npm run build
```

Reset the dev database (keeps the schema, clears the data):

```bash
cd backend && .venv/Scripts/python -c "
from sqlalchemy import text
from app.db.session import engine
t=['ai_evaluations','results','proctor_events','answers','exam_sessions','exam_questions','exams','question_options','questions','subjects','users']
with engine.begin() as c: c.execute(text('TRUNCATE '+', '.join(t)+' RESTART IDENTITY CASCADE'))
print('cleared')" && .venv/Scripts/python -m app.seed
```

## Logs

`logs/backend.log` — everything: auth attempts, access-gate decisions, exam lifecycle,
grading, slow requests (>1 s). `logs/proctor.log` — proctoring only; it is high-volume and
reviewed separately. Both rotate at 5 MB, 5 files kept. Level via `LOG_LEVEL`.

Lines worth grepping:

```
Login: … (examiner/pending)                     auth attempt with role and access status
Access gate blocked … (examiner, status=pending) the gate doing its job
Admin … changed access for … : pending -> approved
Session … started: exam=… questions=10 expires=…
Session … flagged: score=47.5 tab_switches=4
Session … TERMINATED at score 104.0
Session … auto-submitted on timeout
Graded 3 subjective answer(s) in session …
```
