-- Activity library and parent-owned saved activities.
-- Run once in the Supabase SQL editor after reviewing this file.

begin;

create table if not exists public.activities (
  id text primary key,
  slug text not null unique,
  title text not null,
  summary text not null,
  image text not null,
  image_alt text not null,

  age_min_months integer not null,
  age_max_months integer not null,

  kind text not null,
  tags text[] not null default '{}',
  interests text[] not null default '{}',

  duration integer not null,
  setting text not null,
  cost integer not null default 0,
  cost_basis text not null,

  materials text[] not null default '{}',
  steps text[] not null default '{}',
  supervision text not null,

  currency text not null default 'USD',

  status text not null default 'draft',
  review_status text not null
    default 'development fixture — not professionally reviewed',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint valid_activity_id
    check (id ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),

  constraint valid_activity_slug
    check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),

  constraint valid_activity_age_range
    check (
      age_min_months >= 0
      and age_max_months >= age_min_months
      and age_max_months <= 216
    ),

  constraint valid_activity_kind
    check (kind in ('activity', 'outing')),

  constraint valid_activity_interests
    check (
      interests <@ array[
        'animals',
        'art',
        'nature',
        'music',
        'stories',
        'building'
      ]::text[]
    ),

  constraint valid_activity_duration
    check (duration > 0 and duration <= 1440),

  constraint valid_activity_setting
    check (setting in ('indoor', 'outdoor')),

  constraint valid_activity_cost
    check (cost >= 0),

  constraint valid_activity_cost_basis
    check (
      cost_basis in (
        'supplies',
        'admission for one adult and one child'
      )
    ),

  constraint valid_activity_currency
    check (currency ~ '^[A-Z]{3}$'),

  constraint valid_activity_status
    check (status in ('draft', 'approved', 'archived')),

  constraint activity_requires_materials
    check (cardinality(materials) > 0),

  constraint activity_requires_steps
    check (cardinality(steps) > 0)
);


create table if not exists public.saved_activities (
  owner_id uuid not null
    references auth.users(id)
    on delete cascade,

  activity_id text not null
    references public.activities(id)
    on delete cascade,

  created_at timestamptz not null default now(),

  primary key (owner_id, activity_id)
);


create index if not exists activities_status_idx
on public.activities (status);

create index if not exists activities_kind_idx
on public.activities (kind);

create index if not exists activities_age_range_idx
on public.activities (age_min_months, age_max_months);

create index if not exists activities_tags_idx
on public.activities using gin (tags);

create index if not exists activities_interests_idx
on public.activities using gin (interests);

create index if not exists saved_activities_activity_id_idx
on public.saved_activities (activity_id);


create or replace function public.set_activity_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;


drop trigger if exists activities_updated_at
on public.activities;

create trigger activities_updated_at
before update on public.activities
for each row
execute function public.set_activity_updated_at();


alter table public.activities
enable row level security;

alter table public.saved_activities
enable row level security;


revoke all
on table public.activities
from anon, authenticated;

grant select
on table public.activities
to anon, authenticated;


drop policy if exists "Visitors can read approved activities"
on public.activities;

create policy "Visitors can read approved activities"
on public.activities
for select
to anon, authenticated
using (status = 'approved');


revoke all
on table public.saved_activities
from anon, authenticated;

grant select, insert, delete
on table public.saved_activities
to authenticated;


drop policy if exists "Owners can read saved activities"
on public.saved_activities;

create policy "Owners can read saved activities"
on public.saved_activities
for select
to authenticated
using ((select auth.uid()) = owner_id);


drop policy if exists "Owners can save approved activities"
on public.saved_activities;

create policy "Owners can save approved activities"
on public.saved_activities
for insert
to authenticated
with check (
  (select auth.uid()) = owner_id
  and exists (
    select 1
    from public.activities
    where activities.id = saved_activities.activity_id
      and activities.status = 'approved'
  )
);


drop policy if exists "Owners can remove saved activities"
on public.saved_activities;

create policy "Owners can remove saved activities"
on public.saved_activities
for delete
to authenticated
using ((select auth.uid()) = owner_id);

commmit;
