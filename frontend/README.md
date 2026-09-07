# Examina — Frontend

Next.js (App Router) + TypeScript + Tailwind client for the exam platform. For what the
platform does and how the pieces fit together, see the [root README](../README.md).

## Running locally

Needs the backend API up first (see the root README's quick start). Then:

```bash
npm install
npm run dev
```

Open http://localhost:3000. The API base URL comes from `NEXT_PUBLIC_API_URL` in `.env.local`
(defaults to `http://127.0.0.1:8000/api/v1`).

```bash
npm run build   # production build
npm run start   # serve the production build
npm run lint    # eslint
npx tsc --noEmit  # type-check
```

## Layout

```
src/app/          Next.js App Router — one route tree per role (admin/examiner/candidate
                   dashboards), the exam runner (app/exam/[sessionId]), results, login
src/components/   UI primitives (ui.tsx), the live operations dashboard, proctoring preview
src/lib/          API client (api.ts), auth context (auth.tsx), shared types (types.ts),
                   and the MediaPipe proctoring engine (proctor.ts)
public/mediapipe/ Vendored MediaPipe WASM runtime
public/models/    Vendored face_landmarker.task model
```

`proctor.ts` is the client-side proctoring engine: it runs MediaPipe's face landmarker
locally in the browser (no per-session server cost), watches face presence, multiple
faces and head-pose-based gaze, and reports browser behavioural signals (tab switches,
window blur, fullscreen exit, clipboard use). It degrades honestly if the vision model
can't load — behavioural signals keep working, and it stops claiming to see faces rather
than inventing detections.
