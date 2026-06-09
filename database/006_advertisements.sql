CREATE TABLE IF NOT EXISTS public.advertisements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  description text,
  image_url text NOT NULL,
  target_type text NOT NULL DEFAULT 'product',
  target_id uuid,
  target_url text,
  position text NOT NULL DEFAULT 'home_banner',
  priority integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  start_date timestamptz,
  end_date timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  view_count integer NOT NULL DEFAULT 0,
  click_count integer NOT NULL DEFAULT 0,
  budget_amount numeric,
  spent_amount numeric NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'active',
  shop_id uuid,
  created_by uuid
);

ALTER TABLE public.advertisements
  ADD COLUMN IF NOT EXISTS view_count integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS click_count integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS budget_amount numeric,
  ADD COLUMN IF NOT EXISTS spent_amount numeric NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS shop_id uuid,
  ADD COLUMN IF NOT EXISTS created_by uuid;

ALTER TABLE public.advertisements
  DROP CONSTRAINT IF EXISTS advertisements_target_type_check,
  DROP CONSTRAINT IF EXISTS advertisements_position_check,
  DROP CONSTRAINT IF EXISTS advertisements_priority_check,
  DROP CONSTRAINT IF EXISTS advertisements_status_check,
  DROP CONSTRAINT IF EXISTS advertisements_budget_amount_check,
  DROP CONSTRAINT IF EXISTS advertisements_spent_amount_check,
  DROP CONSTRAINT IF EXISTS advertisements_date_range_check,
  DROP CONSTRAINT IF EXISTS advertisements_shop_id_fkey,
  DROP CONSTRAINT IF EXISTS advertisements_created_by_fkey;

ALTER TABLE public.advertisements
  ADD CONSTRAINT advertisements_target_type_check
    CHECK (target_type IN ('product', 'shop', 'external_url', 'none')),
  ADD CONSTRAINT advertisements_position_check
    CHECK (position IN ('home_banner', 'product_list', 'popup', 'checkout_banner')),
  ADD CONSTRAINT advertisements_priority_check
    CHECK (priority >= 0),
  ADD CONSTRAINT advertisements_status_check
    CHECK (status IN ('draft', 'active', 'paused', 'expired')),
  ADD CONSTRAINT advertisements_budget_amount_check
    CHECK (budget_amount IS NULL OR budget_amount >= 0),
  ADD CONSTRAINT advertisements_spent_amount_check
    CHECK (spent_amount >= 0 AND (budget_amount IS NULL OR spent_amount <= budget_amount)),
  ADD CONSTRAINT advertisements_date_range_check
    CHECK (start_date IS NULL OR end_date IS NULL OR start_date <= end_date),
  ADD CONSTRAINT advertisements_shop_id_fkey
    FOREIGN KEY (shop_id) REFERENCES public.shops(id) ON DELETE CASCADE,
  ADD CONSTRAINT advertisements_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;

UPDATE public.advertisements
SET
  status = 'expired',
  is_active = false
WHERE end_date IS NOT NULL
  AND end_date < now();

UPDATE public.advertisements
SET is_active = (status = 'active')
WHERE status <> 'expired';

CREATE INDEX IF NOT EXISTS advertisements_active_position_idx
ON public.advertisements (position, is_active, status, priority DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS advertisements_shop_status_idx
ON public.advertisements (shop_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS advertisements_target_idx
ON public.advertisements (target_type, target_id);

CREATE OR REPLACE FUNCTION public.touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS advertisements_touch_updated_at ON public.advertisements;
CREATE TRIGGER advertisements_touch_updated_at
BEFORE UPDATE ON public.advertisements
FOR EACH ROW
EXECUTE FUNCTION public.touch_updated_at();

CREATE OR REPLACE FUNCTION public.increment_advertisement_view(p_ad_id uuid)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.advertisements
  SET view_count = view_count + 1
  WHERE id = p_ad_id;
$$;

CREATE OR REPLACE FUNCTION public.increment_advertisement_click(p_ad_id uuid)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.advertisements
  SET click_count = click_count + 1
  WHERE id = p_ad_id;
$$;

ALTER TABLE public.advertisements ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can read active advertisements" ON public.advertisements;
DROP POLICY IF EXISTS "Shop owners can read own advertisements" ON public.advertisements;
DROP POLICY IF EXISTS "Shop owners can create advertisements" ON public.advertisements;
DROP POLICY IF EXISTS "Shop owners can update own advertisements" ON public.advertisements;
DROP POLICY IF EXISTS "Shop owners can delete own advertisements" ON public.advertisements;

CREATE POLICY "Anyone can read active advertisements"
ON public.advertisements
FOR SELECT
TO anon, authenticated
USING (
  is_active = true
  AND status = 'active'
);

CREATE POLICY "Shop owners can read own advertisements"
ON public.advertisements
FOR SELECT
TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM public.shops
    WHERE shops.id = advertisements.shop_id
      AND shops.owner_id = auth.uid()
  )
);

CREATE POLICY "Shop owners can create advertisements"
ON public.advertisements
FOR INSERT
TO authenticated
WITH CHECK (
  created_by = auth.uid()
  AND EXISTS (
    SELECT 1
    FROM public.shops
    WHERE shops.id = advertisements.shop_id
      AND shops.owner_id = auth.uid()
  )
);

CREATE POLICY "Shop owners can update own advertisements"
ON public.advertisements
FOR UPDATE
TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM public.shops
    WHERE shops.id = advertisements.shop_id
      AND shops.owner_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.shops
    WHERE shops.id = advertisements.shop_id
      AND shops.owner_id = auth.uid()
  )
);

CREATE POLICY "Shop owners can delete own advertisements"
ON public.advertisements
FOR DELETE
TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM public.shops
    WHERE shops.id = advertisements.shop_id
      AND shops.owner_id = auth.uid()
  )
);

GRANT SELECT ON public.advertisements TO anon, authenticated;
GRANT INSERT, UPDATE, DELETE ON public.advertisements TO authenticated;
GRANT EXECUTE ON FUNCTION public.increment_advertisement_view(uuid) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.increment_advertisement_click(uuid) TO anon, authenticated;
