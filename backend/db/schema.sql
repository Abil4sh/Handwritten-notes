-- Handwritten Notes -- MVP 1 schema
-- Paste into Supabase -> SQL Editor -> New query -> Run

-- ---------------------------------------------------------------
-- profiles: one row per auth user, created automatically on signup
-- ---------------------------------------------------------------
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at  timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1)))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------
-- notes: the semantic content. `content` is JSONB, deliberately --
-- blocks are always read and written as a whole document.
-- ---------------------------------------------------------------
create table if not exists public.notes (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.profiles(id) on delete cascade,
  title        text not null,
  source_type  text not null default 'text' check (source_type in ('text','audio')),
  source_text  text,
  content      jsonb not null,
  content_hash text not null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index if not exists notes_user_updated_idx
  on public.notes (user_id, updated_at desc);

-- ---------------------------------------------------------------
-- renders: a produced PDF. Content addressed, so an identical
-- request finds the existing row instead of re-rendering.
-- ---------------------------------------------------------------
create table if not exists public.renders (
  id           uuid primary key default gen_random_uuid(),
  note_id      uuid not null references public.notes(id) on delete cascade,
  user_id      uuid not null references public.profiles(id) on delete cascade,
  spec         jsonb not null,
  spec_hash    text not null,
  status       text not null default 'pending'
               check (status in ('pending','running','done','failed')),
  storage_path text,
  page_count   int,
  error        text,
  created_at   timestamptz not null default now()
);

create unique index if not exists renders_note_spec_idx
  on public.renders (note_id, spec_hash);

-- ---------------------------------------------------------------
-- Row level security.
-- FastAPI uses the service role key and bypasses all of this, and
-- enforces ownership in its queries instead. These policies are a
-- second layer for anything that ever connects with the anon key.
-- ---------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.notes    enable row level security;
alter table public.renders  enable row level security;

drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles
  for all using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "own notes" on public.notes;
create policy "own notes" on public.notes
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own renders" on public.renders;
create policy "own renders" on public.renders
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ---------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists notes_touch_updated_at on public.notes;
create trigger notes_touch_updated_at
  before update on public.notes
  for each row execute function public.touch_updated_at();
