from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import reset_request_supabase_client, set_request_supabase_client, supabase

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        response = supabase.auth.get_user(credentials.credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user = getattr(response, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    request_client_token = set_request_supabase_client(credentials.credentials)
    try:
        yield {
            "id": user.id,
            "email": user.email,
            "metadata": user.user_metadata or {},
            "access_token": credentials.credentials,
        }
    finally:
        reset_request_supabase_client(request_client_token)


def require_role(*allowed_roles: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        role = current_user.get("metadata", {}).get("role")
        if not role:
            profile = (
                supabase.table("users")
                .select("role")
                .eq("id", current_user["id"])
                .maybe_single()
                .execute()
            )
            role = (profile.data or {}).get("role")

        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        current_user["role"] = role
        return current_user

    return checker
