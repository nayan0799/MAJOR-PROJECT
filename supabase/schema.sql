-- Run this entire file in Supabase SQL Editor.
-- It creates the incident database table, indexes, and a public Storage bucket.

create extension if not exists pgcrypto;

create table if not exists public.incidents (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('pothole','garbage','road_damage','person')),
  confidence double precision not null default 0,
  latitude double precision,
  longitude double precision,
  bus_id text,
  route text,
  status text not null default 'new'
    check (status in ('new','acknowledged','resolved')),
  description text,
  photo text,
  photo_path text,
  created_at timestamptz not null default now()
);

create index if not exists incidents_created_at_idx on public.incidents(created_at desc);
create index if not exists incidents_type_idx on public.incidents(type);
create index if not exists incidents_status_idx on public.incidents(status);

-- Storage bucket for garbage photos.
insert into storage.buckets (id, name, public)
values ('garbage-photos', 'garbage-photos', true)
on conflict (id) do nothing;

-- Public read access for this prototype bucket.
drop policy if exists "Public can view garbage photos" on storage.objects;
create policy "Public can view garbage photos"
on storage.objects for select
using (bucket_id = 'garbage-photos');

-- Upload policy for the prototype. For production, replace this with
-- authenticated-user policies.
drop policy if exists "Prototype can upload garbage photos" on storage.objects;
create policy "Prototype can upload garbage photos"
on storage.objects for insert
with check (bucket_id = 'garbage-photos');

-- Optional: enable RLS on incidents and add proper authenticated policies
-- before production deployment.
