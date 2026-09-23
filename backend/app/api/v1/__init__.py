"""v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai_questions,
    analytics,
    auth,
    exam_sessions,
    exams,
    grading,
    live_signal,
    login_requests,
    proctor,
    question_import,
    questions,
    recruitment,
    results,
    sections,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)

# ── Ordering matters here ────────────────────────────────────────────────
# Starlette matches routes in registration order, so a literal path must be
# registered before any parameterised path that could swallow it. These two
# routers hang literal segments off /questions ("ai-drafts", "ai-generate",
# "import"), while questions.router owns /questions/{question_id} - which
# happily matches the string "ai-drafts" and then fails to parse it as a UUID.
#
# Registering them first is what keeps GET /questions/ai-drafts reaching the
# draft queue instead of returning "question_id: Input should be a valid UUID".
api_router.include_router(ai_questions.router)
api_router.include_router(question_import.router)
api_router.include_router(questions.router)

api_router.include_router(exams.router)
api_router.include_router(sections.router)
api_router.include_router(login_requests.router)
api_router.include_router(exam_sessions.router)
api_router.include_router(proctor.router)
api_router.include_router(live_signal.router)
api_router.include_router(grading.router)
api_router.include_router(results.router)
api_router.include_router(recruitment.router)
api_router.include_router(analytics.router)

__all__ = ["api_router"]
