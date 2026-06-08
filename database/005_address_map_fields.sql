alter table public.address
add column if not exists latitude double precision,
add column if not exists longitude double precision,
add column if not exists map_provider text default 'osm',
add column if not exists provider_place_id text,
add column if not exists raw_address text;

alter table public.address
add constraint address_latitude_range
check (latitude is null or latitude between -90 and 90);

alter table public.address
add constraint address_longitude_range
check (longitude is null or longitude between -180 and 180);