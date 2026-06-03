from contextvars import ContextVar, Token
from functools import lru_cache
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.config import settings


@lru_cache
def get_base_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_service_supabase_client() -> Client:
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for server callbacks")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


_request_client: ContextVar[Client | None] = ContextVar(
    "request_supabase_client",
    default=None,
)


def create_user_supabase_client(access_token: str) -> Client:
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        ClientOptions(
            headers={"Authorization": f"Bearer {access_token}"},
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def get_supabase_client(access_token: str | None = None) -> Client:
    if access_token:
        return create_user_supabase_client(access_token)
    return _request_client.get() or get_base_supabase_client()


def set_request_supabase_client(access_token: str) -> Token[Client | None]:
    return _request_client.set(create_user_supabase_client(access_token))


def reset_request_supabase_client(token: Token[Client | None]) -> None:
    _request_client.reset(token)


class SupabaseProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_supabase_client(), name)


supabase = SupabaseProxy()
