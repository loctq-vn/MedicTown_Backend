create table if not exists public.device_tokens (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null
        references public.users(id)
        on delete cascade,
    token text not null unique,
    platform text not null default 'android',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint device_tokens_platform_check
        check (platform in ('android'))
);

create index if not exists device_tokens_user_id_idx
on public.device_tokens(user_id);

alter table public.device_tokens enable row level security;

-- Android users must not read or modify tokens directly.
revoke all on table public.device_tokens from anon, authenticated;

-- Only the backend service-role client manages this table.
grant select, insert, update, delete
on table public.device_tokens
to service_role;