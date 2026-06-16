create table if not exists public.product_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  event_type text not null check (
    event_type in (
      'view',
      'click',
      'add_to_cart',
      'buy',
      'review',
      'search_click'
    )
  ),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamp with time zone not null default now()
);

create index if not exists product_events_user_created_idx
on public.product_events (user_id, created_at desc);

create index if not exists product_events_product_created_idx
on public.product_events (product_id, created_at desc);

create index if not exists product_events_type_created_idx
on public.product_events (event_type, created_at desc);

alter table public.product_events enable row level security;

drop policy if exists "Users can read own product events"
on public.product_events;

drop policy if exists "Users can create own product events"
on public.product_events;

create policy "Users can read own product events"
on public.product_events
for select
to authenticated
using (
  user_id = auth.uid()
);

create policy "Users can create own product events"
on public.product_events
for insert
to authenticated
with check (
  user_id = auth.uid()
);

grant select, insert on public.product_events to authenticated;
revoke all on public.product_events from anon;
