"""FastAPI routers for sessionized workflow access."""

from fastapi import APIRouter

from backend.app.api.artifacts import create_artifacts_router
from backend.app.api.events import create_events_router
from backend.app.api.health import create_health_router
from backend.app.api.learners import create_learners_router
from backend.app.api.learning_flow import create_learning_flow_router
from backend.app.api.sessions import create_sessions_router
from backend.app.services.session_service import SessionService


def create_api_router(session_service: SessionService) -> APIRouter:
    router = APIRouter()
    router.include_router(create_health_router(session_service))
    router.include_router(create_sessions_router(session_service))
    router.include_router(create_learners_router(session_service))
    router.include_router(create_learning_flow_router(session_service))
    router.include_router(create_events_router(session_service))
    router.include_router(create_artifacts_router(session_service))
    return router
