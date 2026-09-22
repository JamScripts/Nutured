-- Run once in the Supabase SQL editor.
create table if not exists public.child_profiles (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null unique references auth.users(id) on delete cascade,
  nickname text null check (char_length(nickname) <= 40),
  age_band text not null check (age_band in ('baby', '1-2', '3-4', '5-7')),
  interests text[] not null default '{}',
  setting text null check (setting is null or setting in ('indoor', 'outdoor')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint valid_interests check (
    interests <@ array['animals','art','nature','music','stories','building']::text[]
  )
);

alter table public.child_profiles enable row level security;

drop policy if exists "Owners can read child profile" on public.child_profiles;
create policy "Owners can read child profile"
on public.child_profiles for select
to authenticated
using ((select auth.uid()) = owner_id);

drop policy if exists "Owners can create child profile" on public.child_profiles;
create policy "Owners can create child profile"
on public.child_profiles for insert
to authenticated
with check ((select auth.uid()) = owner_id);

drop policy if exists "Owners can update child profile" on public.child_profiles;
create policy "Owners can update child profile"
on public.child_profiles for update
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create or replace function public.set_child_profile_updated_at()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists child_profiles_updated_at on public.child_profiles;
create trigger child_profiles_updated_at
before update on public.child_profiles
for each row execute function public.set_child_profile_updated_at();
