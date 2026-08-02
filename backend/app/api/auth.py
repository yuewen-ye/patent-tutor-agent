from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.app.api.models import (
    AuthResponse,
    ErrorResponse,
    LoginRequest,
    RegisterRequest,
)
from backend.app.persistence.repositories import LearnerRegistrationError
from backend.app.services.session_service import SessionService


def create_auth_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["auth"])

    @router.post(
        "/auth/register",
        response_model=AuthResponse,
        responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
        status_code=status.HTTP_201_CREATED,
    )
    def register(request: RegisterRequest) -> AuthResponse:
        try:
            result = session_service.register_learner(
                login_id=request.login_id,
                password=request.password,
                display_name=request.display_name,
                email=request.email,
            )
        except LearnerRegistrationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "registration_failed", "reason": exc.reason},
            ) from exc
        return AuthResponse.model_validate(result)

    @router.post(
        "/auth/login",
        response_model=AuthResponse,
        responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    def login(request: LoginRequest) -> AuthResponse:
        try:
            result = session_service.authenticate_learner(
                login_id=request.login_id,
                password=request.password,
            )
        except LearnerRegistrationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "authentication_failed", "reason": exc.reason},
            ) from exc
        return AuthResponse.model_validate(result)

    return router