from fastapi import HTTPException, status

from app.database import supabase
from app.schemas.auth_schema import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)


def _build_user_response(user, profile: dict | None = None) -> UserResponse:
    metadata = user.user_metadata or {}
    profile = profile or {}
    return UserResponse(
        id=user.id,
        email=user.email,
        name=profile.get("name") or metadata.get("name") or metadata.get("full_name"),
        phone=profile.get("phone") or metadata.get("phone"),
        role=profile.get("role") or metadata.get("role"),
        user_metadata=metadata,
    )


def register(payload: RegisterRequest) -> AuthResponse:
    metadata = payload.data or {}
    name = payload.name or payload.full_name or metadata.get("name") or metadata.get("full_name")
    phone = payload.phone or metadata.get("phone")
    try:
        response = supabase.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
                "options": {
                    "data": {
                        **metadata,
                        "name": name,
                        "phone": phone,
                        "role": "customer",
                    }
                },
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to register account",
        ) from exc

    if response.user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to register account",
        )

    profile = {
        "id": response.user.id,
        "email": payload.email,
        "name": name,
        "phone": phone,
        "role": "customer",
    }
    supabase.table("users").upsert(profile).execute()

    session = response.session
    return AuthResponse(
        access_token=getattr(session, "access_token", None),
        refresh_token=getattr(session, "refresh_token", None),
        user=_build_user_response(response.user, profile),
    )


def login(payload: LoginRequest) -> AuthResponse:
    try:
        response = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc

    if response.user is None or response.session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    profile_response = (
        supabase.table("users")
        .select("*")
        .eq("id", response.user.id)
        .maybe_single()
        .execute()
    )

    return AuthResponse(
        access_token=response.session.access_token,
        refresh_token=response.session.refresh_token,
        user=_build_user_response(response.user, profile_response.data),
    )


def login_with_google(payload: GoogleLoginRequest) -> AuthResponse:
    try:
        credentials = {
            "provider": "google",
            "token": payload.id_token,
        }
        if payload.nonce:
            credentials["nonce"] = payload.nonce
        response = supabase.auth.sign_in_with_id_token(credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        ) from exc

    if response.user is None or response.session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    profile = {
        "id": response.user.id,
        "email": response.user.email,
        "name": (response.user.user_metadata or {}).get("name")
        or (response.user.user_metadata or {}).get("full_name"),
        "role": "customer",
    }
    supabase.table("users").upsert(profile).execute()

    return AuthResponse(
        access_token=response.session.access_token,
        refresh_token=response.session.refresh_token,
        user=_build_user_response(response.user, profile),
    )
