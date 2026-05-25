from fastapi import HTTPException, status

from app.database import get_supabase_client, supabase
from app.schemas.auth_schema import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)


def _fallback_name(email: str | None, name: str | None = None) -> str:
    if name:
        return name
    if email and "@" in email:
        return email.split("@", 1)[0]
    return "User"


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


def _ensure_profile(access_token: str | None, profile: dict) -> dict:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A login session is required to create the user profile",
        )

    user_supabase = get_supabase_client(access_token)
    existing_response = (
        user_supabase.table("users")
        .select("*")
        .eq("id", profile["id"])
        .maybe_single()
        .execute()
    )
    if existing_response.data:
        return existing_response.data

    response = user_supabase.table("users").insert(profile).execute()
    user_profile = (response.data or [None])[0]
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create user profile",
        )
    return user_profile


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
        "name": _fallback_name(payload.email, name),
        "phone": phone,
        "role": "customer",
    }

    session = response.session
    profile = _ensure_profile(getattr(session, "access_token", None), profile)
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

    metadata = response.user.user_metadata or {}
    profile = _ensure_profile(
        response.session.access_token,
        {
            "id": response.user.id,
            "email": response.user.email,
            "name": _fallback_name(
                response.user.email,
                metadata.get("name") or metadata.get("full_name"),
            ),
            "phone": metadata.get("phone"),
            "role": "customer",
        },
    )

    return AuthResponse(
        access_token=response.session.access_token,
        refresh_token=response.session.refresh_token,
        user=_build_user_response(response.user, profile),
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
        "name": _fallback_name(
            response.user.email,
            (response.user.user_metadata or {}).get("name")
            or (response.user.user_metadata or {}).get("full_name"),
        ),
        "role": "customer",
    }
    profile = _ensure_profile(response.session.access_token, profile)

    return AuthResponse(
        access_token=response.session.access_token,
        refresh_token=response.session.refresh_token,
        user=_build_user_response(response.user, profile),
    )
