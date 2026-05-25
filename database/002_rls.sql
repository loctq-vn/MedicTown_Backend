-- MedicTown Row Level Security policies.
-- These policies assume database requests run with the authenticated user's JWT
-- so auth.uid() resolves to the current user.

-- USERS
alter table public.users enable row level security;

drop policy if exists "Users can read own profile" on public.users;
drop policy if exists "Users can insert own profile" on public.users;
drop policy if exists "Users can update own profile" on public.users;
drop policy if exists "Users can delete own profile" on public.users;

create policy "Users can read own profile"
on public.users
for select
to authenticated
using (
  id = auth.uid()
);

create policy "Users can insert own profile"
on public.users
for insert
to authenticated
with check (
  id = auth.uid()
  and coalesce(role, 'customer') = 'customer'
);

create policy "Users can update own profile"
on public.users
for update
to authenticated
using (
  id = auth.uid()
)
with check (
  id = auth.uid()
);

revoke update on public.users from authenticated;

grant update (name, phone, avatar_url)
on public.users
to authenticated;

-- ADDRESS
alter table public.address enable row level security;

drop policy if exists "Users can read own addresses" on public.address;
drop policy if exists "Users can insert own addresses" on public.address;
drop policy if exists "Users can update own addresses" on public.address;
drop policy if exists "Users can delete own addresses" on public.address;

create policy "Users can read own addresses"
on public.address
for select
to authenticated
using (
  user_id = auth.uid()
);

create policy "Users can insert own addresses"
on public.address
for insert
to authenticated
with check (
  user_id = auth.uid()
);

create policy "Users can update own addresses"
on public.address
for update
to authenticated
using (
  user_id = auth.uid()
)
with check (
  user_id = auth.uid()
);

create policy "Users can delete own addresses"
on public.address
for delete
to authenticated
using (
  user_id = auth.uid()
);

-- CART ITEMS
alter table public.cart_items enable row level security;

drop policy if exists "Users can read own cart items" on public.cart_items;
drop policy if exists "Users can insert own cart items" on public.cart_items;
drop policy if exists "Users can update own cart items" on public.cart_items;
drop policy if exists "Users can delete own cart items" on public.cart_items;

create policy "Users can read own cart items"
on public.cart_items
for select
to authenticated
using (
  user_id = auth.uid()
);

create policy "Users can insert own cart items"
on public.cart_items
for insert
to authenticated
with check (
  user_id = auth.uid()
);

create policy "Users can update own cart items"
on public.cart_items
for update
to authenticated
using (
  user_id = auth.uid()
)
with check (
  user_id = auth.uid()
);

create policy "Users can delete own cart items"
on public.cart_items
for delete
to authenticated
using (
  user_id = auth.uid()
);

-- SHOPS
alter table public.shops enable row level security;

drop policy if exists "Anyone can read active shops" on public.shops;
drop policy if exists "Owners can read own shops" on public.shops;
drop policy if exists "Users can create own shops" on public.shops;
drop policy if exists "Owners can update own shops" on public.shops;

create policy "Anyone can read active shops"
on public.shops
for select
to anon, authenticated
using (
  is_active = true
);

create policy "Owners can read own shops"
on public.shops
for select
to authenticated
using (
  owner_id = auth.uid()
);

create policy "Users can create own shops"
on public.shops
for insert
to authenticated
with check (
  owner_id = auth.uid()
);

create policy "Owners can update own shops"
on public.shops
for update
to authenticated
using (
  owner_id = auth.uid()
)
with check (
  owner_id = auth.uid()
);

-- PRODUCTS
alter table public.products enable row level security;

drop policy if exists "Anyone can read active products" on public.products;
drop policy if exists "Shop owners can read own products" on public.products;
drop policy if exists "Shop owners can create products" on public.products;
drop policy if exists "Shop owners can update own products" on public.products;
drop policy if exists "Shop owners can delete own products" on public.products;

create policy "Anyone can read active products"
on public.products
for select
to anon, authenticated
using (
  is_active = true
);

create policy "Shop owners can read own products"
on public.products
for select
to authenticated
using (
  exists (
    select 1
    from public.shops
    where shops.id = products.shop_id
      and shops.owner_id = auth.uid()
  )
);

create policy "Shop owners can create products"
on public.products
for insert
to authenticated
with check (
  exists (
    select 1
    from public.shops
    where shops.id = products.shop_id
      and shops.owner_id = auth.uid()
  )
);

create policy "Shop owners can update own products"
on public.products
for update
to authenticated
using (
  exists (
    select 1
    from public.shops
    where shops.id = products.shop_id
      and shops.owner_id = auth.uid()
  )
)
with check (
  exists (
    select 1
    from public.shops
    where shops.id = products.shop_id
      and shops.owner_id = auth.uid()
  )
);

create policy "Shop owners can delete own products"
on public.products
for delete
to authenticated
using (
  exists (
    select 1
    from public.shops
    where shops.id = products.shop_id
      and shops.owner_id = auth.uid()
  )
);

-- ORDERS
alter table public.orders enable row level security;

drop policy if exists "Customers can read own orders" on public.orders;
drop policy if exists "Shop owners can read shop orders" on public.orders;
drop policy if exists "Customers can create own orders" on public.orders;
drop policy if exists "Shop owners can update shop orders" on public.orders;

create policy "Customers can read own orders"
on public.orders
for select
to authenticated
using (
  user_id = auth.uid()
);

create policy "Shop owners can read shop orders"
on public.orders
for select
to authenticated
using (
  exists (
    select 1
    from public.shops
    where shops.id = orders.shop_id
      and shops.owner_id = auth.uid()
  )
);

create policy "Customers can create own orders"
on public.orders
for insert
to authenticated
with check (
  user_id = auth.uid()
);

create policy "Shop owners can update shop orders"
on public.orders
for update
to authenticated
using (
  exists (
    select 1
    from public.shops
    where shops.id = orders.shop_id
      and shops.owner_id = auth.uid()
  )
)
with check (
  exists (
    select 1
    from public.shops
    where shops.id = orders.shop_id
      and shops.owner_id = auth.uid()
  )
);

-- ORDER ITEMS
alter table public.order_items enable row level security;

drop policy if exists "Customers can read own order items" on public.order_items;
drop policy if exists "Shop owners can read shop order items" on public.order_items;
drop policy if exists "Customers can create own order items" on public.order_items;

create policy "Customers can read own order items"
on public.order_items
for select
to authenticated
using (
  exists (
    select 1
    from public.orders
    where orders.id = order_items.order_id
      and orders.user_id = auth.uid()
  )
);

create policy "Shop owners can read shop order items"
on public.order_items
for select
to authenticated
using (
  exists (
    select 1
    from public.orders
    join public.shops on shops.id = orders.shop_id
    where orders.id = order_items.order_id
      and shops.owner_id = auth.uid()
  )
);

create policy "Customers can create own order items"
on public.order_items
for insert
to authenticated
with check (
  exists (
    select 1
    from public.orders
    where orders.id = order_items.order_id
      and orders.user_id = auth.uid()
  )
);

-- PAYMENTS
alter table public.payments enable row level security;

drop policy if exists "Customers can read own payments" on public.payments;
drop policy if exists "Shop owners can read shop payments" on public.payments;
drop policy if exists "Customers can create own payments" on public.payments;

create policy "Customers can read own payments"
on public.payments
for select
to authenticated
using (
  exists (
    select 1
    from public.orders
    where orders.id = payments.order_id
      and orders.user_id = auth.uid()
  )
);

create policy "Shop owners can read shop payments"
on public.payments
for select
to authenticated
using (
  exists (
    select 1
    from public.orders
    join public.shops on shops.id = orders.shop_id
    where orders.id = payments.order_id
      and shops.owner_id = auth.uid()
  )
);

create policy "Customers can create own payments"
on public.payments
for insert
to authenticated
with check (
  exists (
    select 1
    from public.orders
    where orders.id = payments.order_id
      and orders.user_id = auth.uid()
  )
);

-- REVIEWS
alter table public.reviews enable row level security;

drop policy if exists "Anyone can read reviews" on public.reviews;
drop policy if exists "Users can create own reviews" on public.reviews;
drop policy if exists "Users can update own reviews" on public.reviews;
drop policy if exists "Users can delete own reviews" on public.reviews;

create policy "Anyone can read reviews"
on public.reviews
for select
to anon, authenticated
using (
  true
);

create policy "Users can create own reviews"
on public.reviews
for insert
to authenticated
with check (
  user_id = auth.uid()
  and exists (
    select 1
    from public.order_items
    join public.orders on orders.id = order_items.order_id
    where order_items.id = reviews.order_item_id
      and orders.user_id = auth.uid()
      and orders.status = 'completed'
  )
);

create policy "Users can update own reviews"
on public.reviews
for update
to authenticated
using (
  user_id = auth.uid()
)
with check (
  user_id = auth.uid()
);

create policy "Users can delete own reviews"
on public.reviews
for delete
to authenticated
using (
  user_id = auth.uid()
);
