alter table public.orders
add column if not exists stock_deducted_at timestamp with time zone,
add column if not exists stock_restored_at timestamp with time zone;

create or replace function public.confirm_shop_order_and_deduct_stock(
  p_shop_id uuid,
  p_order_id uuid
)
returns public.orders
language plpgsql
set search_path = public
as $$
declare
  v_order public.orders%rowtype;
  v_item record;
  v_product public.products%rowtype;
  v_item_count integer;
begin
  select *
  into v_order
  from public.orders
  where id = p_order_id
    and shop_id = p_shop_id
  for update;

  if not found then
    raise exception 'Order not found' using errcode = 'P0002';
  end if;

  if lower(coalesce(v_order.status, '')) <> 'pending' then
    raise exception 'Invalid order status transition: % -> confirmed', coalesce(v_order.status, 'unknown')
      using errcode = 'P0001';
  end if;

  if v_order.stock_deducted_at is not null then
    raise exception 'Order stock has already been deducted' using errcode = 'P0001';
  end if;

  select count(*)
  into v_item_count
  from public.order_items
  where order_id = p_order_id;

  if v_item_count = 0 then
    raise exception 'Order has no items' using errcode = 'P0001';
  end if;

  for v_item in
    select product_id, sum(quantity)::integer as quantity
    from public.order_items
    where order_id = p_order_id
    group by product_id
  loop
    if v_item.quantity <= 0 then
      raise exception 'Invalid quantity for product %', v_item.product_id
        using errcode = 'P0001';
    end if;

    select *
    into v_product
    from public.products
    where id = v_item.product_id
      and shop_id = p_shop_id
    for update;

    if not found then
      raise exception 'Product % not found in shop', v_item.product_id
        using errcode = 'P0002';
    end if;

    if coalesce(v_product.is_active, false) is false then
      raise exception 'Product % is not active', v_item.product_id
        using errcode = 'P0001';
    end if;

    if coalesce(v_product.stock, 0) < v_item.quantity then
      raise exception 'Quantity exceeds product stock for product %', v_item.product_id
        using errcode = 'P0001';
    end if;

    update public.products
    set stock = stock - v_item.quantity
    where id = v_item.product_id;
  end loop;

  update public.orders
  set
    status = 'confirmed',
    stock_deducted_at = now(),
    stock_restored_at = null,
    updated_at = now()
  where id = p_order_id
  returning * into v_order;

  return v_order;
end;
$$;

create or replace function public.cancel_shop_order_and_restore_stock(
  p_shop_id uuid,
  p_order_id uuid
)
returns public.orders
language plpgsql
set search_path = public
as $$
declare
  v_order public.orders%rowtype;
  v_item record;
begin
  select *
  into v_order
  from public.orders
  where id = p_order_id
    and shop_id = p_shop_id
  for update;

  if not found then
    raise exception 'Order not found' using errcode = 'P0002';
  end if;

  if lower(coalesce(v_order.status, '')) = 'cancelled' then
    return v_order;
  end if;

  if lower(coalesce(v_order.status, '')) not in ('pending', 'confirmed', 'shipping') then
    raise exception 'Invalid order status transition: % -> cancelled', coalesce(v_order.status, 'unknown')
      using errcode = 'P0001';
  end if;

  if v_order.stock_deducted_at is not null and v_order.stock_restored_at is null then
    for v_item in
      select product_id, sum(quantity)::integer as quantity
      from public.order_items
      where order_id = p_order_id
      group by product_id
    loop
      update public.products
      set stock = stock + v_item.quantity
      where id = v_item.product_id
        and shop_id = p_shop_id;
    end loop;
  end if;

  update public.orders
  set
    status = 'cancelled',
    stock_restored_at = case
      when stock_deducted_at is not null and stock_restored_at is null then now()
      else stock_restored_at
    end,
    updated_at = now()
  where id = p_order_id
  returning * into v_order;

  return v_order;
end;
$$;

revoke all on function public.confirm_shop_order_and_deduct_stock(uuid, uuid) from public;
revoke all on function public.cancel_shop_order_and_restore_stock(uuid, uuid) from public;

grant execute on function public.confirm_shop_order_and_deduct_stock(uuid, uuid) to authenticated, service_role;
grant execute on function public.cancel_shop_order_and_restore_stock(uuid, uuid) to authenticated, service_role;
