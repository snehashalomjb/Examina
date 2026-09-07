# ExamAI — AI-Based Intelligent Examination Platform with Automated Proctoring and Candidate Performance Analysis

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Tasks_Vision-0078D7?logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![ReportLab](https://img.shields.io/badge/ReportLab-5.0+-C0392B)](https://www.reportlab.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)

An enterprise-grade, full-stack online examination platform featuring a **structured question bank (10 question types)**, **dual examination modes (Academic & Corporate with 12 blueprints)**, a **server-authoritative timed exam engine**, **real-time client-side AI proctoring via Google MediaPipe**, an **automated objective + LLM subjective grading pipeline**, a **live dark-mode operations monitoring dashboard**, and **certified PDF scorecard generation**.

---

## 🌟 Key Highlights & Features

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🎓 DUAL EXAMINATION MODES (12 Blueprints)                                  │
│  • Academic Mode: Semester, Midterm, Unit Test, Lab Viva, Entrance, Remedial│
│  • Corporate Mode: Campus Drive, Core Eng, Data/AI, SDET, Fast-Track, Senior │
├──────────────────────────────────────────────────────────────────────────────┤
│  📚 STRUCTURED QUESTION BANK (10 Supported Types)                            │
│  • MCQ (Single Choice), Multi-Select, True/False, Fill Blank, Numerical      │
│  • Short Answer, Long Answer, Handwritten Upload (OCR), Passage, Coding      │
├──────────────────────────────────────────────────────────────────────────────┤
│  🛡️ CLIENT-SIDE AI PROCTORING & ZERO-CHEAT ENFORCEMENT                       │
│  • MediaPipe FaceLandmarker (Face Presence, Multi-Face, Gaze & 3D Head Pose) │
│  • Blocked Clipboard (Zero Cut/Copy/Paste), Right-Click Lock, Fullscreen     │
│  • Tab-Switch & Blur Tracking with Millisecond Duration Logging              │
│  • Frame Luminance Lens Obstruction & Blackout Detection                    │
├──────────────────────────────────────────────────────────────────────────────┤
│  🤖 DUAL-STAGE EVALUATION ENGINE & PDF CERTIFICATION                         │
│  • Instant Auto-Evaluation for Objective & Numerical (Tolerance-Aware)       │
│  • LLM First-Pass Scoring with Rubric Justification (GPT-4o / Claude / Stub)│
│  • Examiner Grading Queue with Question-Grouped Batch Review & Annotations   │
│  • Publication-Grade Certified PDF Scorecard Generation (ReportLab)         │
├──────────────────────────────────────────────────────────────────────────────┤
│  🖥️ LIVE OPERATIONS DASHBOARD (Section 6 Layout)                             │
│  • Real-time candidate telemetry, live active session stream, proctor alerts │
│  • Cohort signal breakdown progress bars & Score distribution histogram     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start Guide

### Prerequisites
* **Docker Desktop** (PostgreSQL & MinIO storage)
* **Python 3.12+** & **Node.js 20+**
* [uv package manager](https://docs.astral.sh/uv/) (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
* [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) *(Optional: for handwritten scan OCR)*

### 1. Start Infrastructure (PostgreSQL & MinIO)
```bash
docker compose up -d db db_test minio
```

### 2. Configure Environment
```bash
cp .env.example .env
```

### 3. Setup & Run Backend API
```bash
cd backend
uv venv --python 3.12
# Windows: .venv\Scripts\activate | Linux/macOS: source .venv/bin/activate
uv pip install -e ".[dev]"
uv run python -m alembic upgrade head
uv run python -m app.seed
uv run python -m uvicorn app.main:app --reload --port 8000
```

### 4. Setup & Run Next.js Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 🌐 Application URLs & Endpoints

| Service | Local URL | Default Credentials / Purpose |
| :--- | :--- | :--- |
| **Next.js Web Portal** | `http://localhost:3000` | Main Student & Examiner Interface |
| **Interactive API Docs (Swagger)** | `http://127.0.0.1:8000/docs` | FastAPI REST & WebSocket Endpoints |
| **Alternative API Docs (ReDoc)** | `http://127.0.0.1:8000/redoc` | OpenAPI Specifications |
| **MinIO Object Console** | `http://localhost:9001` | `minioadmin` / `minioadmin` |
| **PostgreSQL Database** | `localhost:5433` | Database: `examdb` (User: `exam`, Pass: `exam`) |
| **Test Database** | `localhost:5434` | Database: `examdb_test` |

---

## 👤 Pre-Seeded Demo Accounts

| Role | Email Address | Password | Permissions & Notes |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@exam.edu` | `Admin@12345` | System oversight, user approvals & live monitoring |
| **Examiner** | `examiner@exam.edu` | `Passw0rd!` | Exam builder, question bank authoring & grading portal |
| **Pending Examiner** | `pending.examiner@exam.edu` | `Passw0rd!` | **Access Gated** (approvable via Admin portal) |
| **Candidate 1** | `candidate1@exam.edu` | `Passw0rd!` | Enrolled in Academic & Corporate exams |
| **Candidate 2** | `candidate2@exam.edu` | `Passw0rd!` | Active test account |
| **Candidate 3** | `candidate3@exam.edu` | `Passw0rd!` | Active test account |

---

## 🏛️ System Architecture & Data Flow

```mermaid
flowchart TD
    subgraph Client ["Frontend Layer (Next.js & MediaPipe)"]
        S1[Student Login / JWT Gating] --> S2[Secure Exam Interface]
        S2 --> S3[MediaPipe Vision Engine<br/>Face, Gaze & Multi-Face]
        S2 --> S4[Anti-Cheat Listeners<br/>0 Copy/Paste, Fullscreen, Blur]
        S2 -->|Live Autosave| S5[Answer Submission Stream]
        S3 -->|Heartbeat Every 10s| S6[Proctor Telemetry Payload]
        S4 --> S6
    end

    subgraph Backend ["Backend Layer (FastAPI & PostgreSQL)"]
        S1 --> B1[JWT & Role Verification]
        B1 --> B2[Deterministic Paper Generator<br/>Salted Random Seed per Candidate]
        B2 --> S2
        S6 --> B3[Proctor Ingest & Suspicion Engine<br/>0–100 Normalized Score]
        B3 -->|Threshold Warning / Termination| S2
        B3 --> B4[(PostgreSQL proctor_events)]
        
        S5 -->|Submission / Timeout| B5[Auto-Evaluation Engine]
        B5 -->|Objective Questions| B6[MCQ & Numerical Auto-Scoring]
        B5 -->|Subjective Questions| B7[LLM Evaluator GPT-4o / Claude]
        B5 -->|Handwritten Scans| B8[Tesseract OCR Pre-Processor]
        B8 --> B7
    end

    subgraph Operations ["Operations & Staff Layer"]
        B6 --> O1[Examiner Grading Portal]
        B7 --> O1
        B4 --> O2[Live Operations Dashboard (Section 6)]
        O1 -->|Review & Publish| O3[Result Publishing Engine]
        O3 --> O4[ReportLab PDF Scorecard Generator]
        O4 --> O5[Student Results Dashboard & Scorecard PDF]
    end
```

---

## 🧩 In-Depth Feature Architecture

### 1. Dual Examination Modes & 12 Pre-Built Blueprints
The platform supports two distinct evaluation paradigms:
* **Academic Examination Mode**:
  1. `Semester End Comprehensive Examination` (Theory + Numerical + Diagram)
  2. `Mid-Semester Assessment`
  3. `Continuous Unit Test` (Speed MCQ)
  4. `Laboratory Viva & Code Assessment` (Algorithm & Coding)
  5. `University Entrance & Scholarship Test` (Negative marking enabled)
  6. `Remedial & Makeup Examination`
* **Corporate Hiring Mode**:
  1. `Full-Stack Software Engineer Campus Drive` (Aptitude, Tech, Coding)
  2. `Core Engineering Assessment` (Systems & OS)
  3. `Data Science & AI/ML Specialist Track` (Stats, ML, Python)
  4. `QA & SDET Assessment` (Test automation, logic)
  5. `Fast-Track Screening Assessment` (30-min rapid filter)
  6. `Senior Technical Architect Assessment` (System design & long answer)

### 2. Client-Side AI Proctoring Engine (`frontend/src/lib/proctor.ts`)
* **Google MediaPipe Tasks-Vision** runs client-side via WebAssembly (WASM) and WebGL/GPU acceleration.
* **Gaze & 3D Head-Pose Estimation**: Calculates yaw and pitch angles from facial mesh landmarks (`NOSE_TIP`, `EYE_OUTER`, `SILHOUETTE`, `CHIN`). Flags `gaze_away` if candidate looks down at a phone or notes.
* **Multi-Face Detection**: Detects if a secondary person enters the webcam frame (`multiple_faces`).
* **Absence Detection**: Flags `face_missing` if face is not present for >2 seconds.
* **Camera Obstruction / Luminance Filter**: Detects lens blocking or blackout (`camera_blocked`).
* **Zero Clipboard & Anti-Cheat**: Completely blocks `Ctrl+C`, `Ctrl+X`, `Ctrl+V`, right-click context menu, and disables text selection.

### 3. Live Assessment Operations Dashboard (`frontend/src/components/LiveOperationsDashboard.tsx`)
A dedicated dark-themed operations dashboard providing:
* **Top 5 KPI Metrics**: Active Sessions, Exams Today, Flagged Sessions, Grading Queue (with AI pre-scored count), and Cohort Average Score.
* **Live Candidate Feed**: Live countdown timers (`42:17`), question progress (`Q14/30`), and suspicion status badges (`score 12`, `⚠️ susp 42`, `⚠️ susp 78`).
* **Proctoring Alert Stream**: Real-time infraction notifications (`Multiple faces detected`, `Tab switch × 4`, `Prolonged gaze away`, `Face absent 18 s`) with suspicion increments.
* **Cohort Signal Analytics & Score Histogram**: Signal compliance progress bars and completed exam score distribution bar charts.
* **AI Grading Queue Preview**: Grouped question cards (`short`, `long`, `image`) with pre-filled AI evaluation scores and direct review actions.

### 4. Certified PDF Scorecard Generator (`backend/app/services/pdf_generator.py`)
* Uses **ReportLab** to generate high-resolution, certified PDF transcripts:
  * Institutional header and candidate profile
  * Executive score summary tiles (Score, Percentage, Cohort Percentile, AI Proctoring Clearance)
  * Section-by-section breakdown table
  * Question-by-question scoring, candidate answer snippets, and examiner remarks
  * Direct one-click download in candidate result pages (`/results/[resultId]/pdf`).

---

## 🧪 Automated Testing & Code Quality

### Run Backend Unit & Integration Tests
```bash
cd backend
uv run pytest
```
* **Coverage**: Question validation, paper determinism, negative marking, suspicion scoring decay, LLM grading stub, role authorization, and PDF binary export.

### Type Checking & Frontend Linting
```bash
cd frontend
npx tsc --noEmit
npm run lint
```

---

## 📂 Repository Structure

```
AI_Based_Examination_platform/
├── backend/
│   ├── app/
│   │   ├── api/v1/         # REST & WebSocket route handlers (auth, exams, proctor, results, analytics)
│   │   ├── core/           # Security, JWT tokens, config, storage, and logging
│   │   ├── db/models/      # SQLAlchemy 2.0 relational models
│   │   ├── schemas/        # Pydantic v2 schemas
│   │   ├── services/       # Exam engine, auto-evaluator, suspicion, PDF generator, OCR, grading/
│   │   ├── seed.py         # 240+ questions, 9 subjects, 12 active exams
│   │   └── tests/          # Pytest suite with isolated test DB
│   ├── alembic/            # Database schema migrations
│   └── pyproject.toml      # Python dependencies and build metadata
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js App Router (dashboard, exam runner, results, login)
│   │   ├── components/     # UI primitives, LiveOperationsDashboard, LowPoly, Hero, Modals
│   │   └── lib/            # MediaPipe proctoring engine, API client, auth context, types
│   ├── public/             # MediaPipe WASM binaries and face_landmarker.task model
│   └── package.json        # Frontend dependencies
├── docker-compose.yml      # Multi-container setup (PostgreSQL app + test, MinIO)
└── README.md               # Project documentation
```

---

## 📄 License & Attribution
Developed as an Advanced AI-Based Intelligent Examination & Proctoring Platform. Designed for modern higher education institutions, competitive entrance examinations, and corporate recruitment pipelines.
