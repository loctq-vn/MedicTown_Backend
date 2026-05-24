from fastapi import APIRouter

from app.schemas.auth_schema import AuthResponse, GoogleLoginRequest, LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter()


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    return auth_service.register(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    return auth_service.login(payload)


@router.post("/google", response_model=AuthResponse)
def login_with_google(payload: GoogleLoginRequest) -> AuthResponse:
    return auth_service.login_with_google(payload)
