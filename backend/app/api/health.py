from __future__ import annotations

from fastapi import APIRouter, Response, status

from backend.app.api.models import HealthResponse, HealthSessionCounts, ReadinessResponse
from backend.app.services.session_service import SessionService


def create_health_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get(
        "/health",
        response_model=HealthResponse,
        description="Report process liveness and in-memory session counts.",
    )
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            sessions=HealthSessionCounts.model_validate(session_service.session_counts()),
        )

    @router.get(
        "/health/ready",
        response_model=ReadinessResponse,
        description="Report whether this process can accept new workflow sessions.",
    )
    def readiness(response: Response) -> ReadinessResponse:
        result = ReadinessResponse.model_validate(session_service.readiness())
        if not result.ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return result

    return router
