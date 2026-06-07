-- =========================================================
-- CHAT TABLES
-- =========================================================

create table if not exists public.chat_conversations (
  id uuid primary key default uuid_generate_v4(),
  shop_id uuid not null references public.shops(id),
  customer_id uuid not null references public.users(id),
  last_message_at timestamp with time zone,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint chat_conversations_one_per_customer unique (customer_id)
);

create table if not exists public.chat_messages (
  id uuid primary key default uuid_generate_v4(),
  conversation_id uuid not null
    references public.chat_conversations(id)
    on delete cascade,
  sender_id uuid not null references public.users(id),
  sender_type character varying(20) not null,
  content text not null,
  message_type character varying(20) not null default 'text',
  client_message_id uuid not null,
  read_at timestamp with time zone,
  created_at timestamp with time zone not null default now(),
  deleted_at timestamp with time zone,
  constraint chat_messages_sender_type_check
    check (sender_type in ('customer', 'seller')),
  constraint chat_messages_type_check
    check (message_type in ('text')),
  constraint chat_messages_content_check
    check (char_length(trim(content)) between 1 and 4000),
  constraint chat_messages_sender_client_id_unique
    unique (sender_id, client_message_id)
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.chat_conversations'::regclass
      and conname = 'chat_conversations_one_per_customer'
  ) then
    alter table public.chat_conversations
      add constraint chat_conversations_one_per_customer
      unique (customer_id);
  end if;
end;
$$;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.chat_messages'::regclass
      and conname = 'chat_messages_sender_client_id_unique'
  ) then
    alter table public.chat_messages
      add constraint chat_messages_sender_client_id_unique
      unique (sender_id, client_message_id);
  end if;
end;
$$;

create index if not exists chat_conversations_shop_last_message_idx
on public.chat_conversations (shop_id, last_message_at desc);

create index if not exists chat_messages_conversation_created_idx
on public.chat_messages (conversation_id, created_at desc, id);

create index if not exists chat_messages_unread_idx
on public.chat_messages (conversation_id, sender_type, created_at)
where read_at is null and deleted_at is null;

-- Keep conversation ordering server-controlled whenever a message is inserted.
create or replace function public.touch_chat_conversation()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.chat_conversations
  set
    last_message_at = new.created_at,
    updated_at = now()
  where id = new.conversation_id;

  return new;
end;
$$;

drop trigger if exists chat_messages_touch_conversation
on public.chat_messages;

create trigger chat_messages_touch_conversation
after insert on public.chat_messages
for each row
execute function public.touch_chat_conversation();

-- =========================================================
-- CHAT RLS
-- =========================================================

alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

drop policy if exists "Customers can read own chat conversation"
on public.chat_conversations;
drop policy if exists "Shop owners can read shop chat conversations"
on public.chat_conversations;
drop policy if exists "Customers can create own chat conversation"
on public.chat_conversations;

create policy "Customers can read own chat conversation"
on public.chat_conversations
for select
to authenticated
using (
  customer_id = auth.uid()
);

create policy "Shop owners can read shop chat conversations"
on public.chat_conversations
for select
to authenticated
using (
  exists (
    select 1
    from public.shops
    where shops.id = chat_conversations.shop_id
      and shops.owner_id = auth.uid()
      and shops.is_active = true
  )
);

drop policy if exists "Chat participants can read messages"
on public.chat_messages;
drop policy if exists "Chat participants can send messages"
on public.chat_messages;
drop policy if exists "Recipients can mark messages as read"
on public.chat_messages;

create policy "Chat participants can read messages"
on public.chat_messages
for select
to authenticated
using (
  exists (
    select 1
    from public.chat_conversations
    where chat_conversations.id = chat_messages.conversation_id
      and (
        chat_conversations.customer_id = auth.uid()
        or exists (
          select 1
          from public.shops
          where shops.id = chat_conversations.shop_id
            and shops.owner_id = auth.uid()
            and shops.is_active = true
        )
      )
  )
);

create policy "Chat participants can send messages"
on public.chat_messages
for insert
to authenticated
with check (
  sender_id = auth.uid()
  and read_at is null
  and deleted_at is null
  and (
    (
      sender_type = 'customer'
      and exists (
        select 1
        from public.chat_conversations
        where chat_conversations.id = chat_messages.conversation_id
          and chat_conversations.customer_id = auth.uid()
      )
    )
    or
    (
      sender_type = 'seller'
      and exists (
        select 1
        from public.chat_conversations
        join public.shops
          on shops.id = chat_conversations.shop_id
        where chat_conversations.id = chat_messages.conversation_id
          and shops.owner_id = auth.uid()
          and shops.is_active = true
      )
    )
  )
);

create policy "Recipients can mark messages as read"
on public.chat_messages
for update
to authenticated
using (
  read_at is null
  and (
    (
      sender_type = 'seller'
      and exists (
        select 1
        from public.chat_conversations
        where chat_conversations.id = chat_messages.conversation_id
          and chat_conversations.customer_id = auth.uid()
      )
    )
    or
    (
      sender_type = 'customer'
      and exists (
        select 1
        from public.chat_conversations
        join public.shops
          on shops.id = chat_conversations.shop_id
        where chat_conversations.id = chat_messages.conversation_id
          and shops.owner_id = auth.uid()
          and shops.is_active = true
      )
    )
  )
)
with check (
  read_at is not null
  and (
    (
      sender_type = 'seller'
      and exists (
        select 1
        from public.chat_conversations
        where chat_conversations.id = chat_messages.conversation_id
          and chat_conversations.customer_id = auth.uid()
      )
    )
    or
    (
      sender_type = 'customer'
      and exists (
        select 1
        from public.chat_conversations
        join public.shops
          on shops.id = chat_conversations.shop_id
        where chat_conversations.id = chat_messages.conversation_id
          and shops.owner_id = auth.uid()
          and shops.is_active = true
      )
    )
  )
);

-- Only read_at may be changed by authenticated clients. Message content,
-- sender identity and conversation ownership remain immutable.
revoke update on public.chat_conversations from authenticated;
revoke delete on public.chat_conversations from authenticated;
revoke insert on public.chat_conversations from authenticated;
revoke update on public.chat_messages from authenticated;
revoke delete on public.chat_messages from authenticated;

grant select on public.chat_conversations to authenticated;
grant select, insert on public.chat_messages to authenticated;
grant update (read_at) on public.chat_messages to authenticated;
