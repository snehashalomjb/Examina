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
    login_requests,
    proctor,
    questions,
    recruitment,
    results,
    sections,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(questions.router)
api_router.include_router(exams.router)
api_router.include_router(sections.router)
api_router.include_router(login_requests.router)
api_router.include_router(exam_sessions.router)
api_router.include_router(proctor.router)
api_router.include_router(grading.router)
api_router.include_router(results.router)
api_router.include_router(recruitment.router)
api_router.include_router(ai_questions.router)
api_router.include_router(analytics.router)

__all__ = ["api_router"]
