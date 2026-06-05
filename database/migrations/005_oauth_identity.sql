-- LvL social login identity bridge.
-- Run in Supabase SQL editor before enabling OAuth registration in production.

alter table public.users
  add column if not exists supabase_auth_user_id uuid,
  add column if not exists oauth_provider text,
  add column if not exists oauth_subject text,
  add column if not exists oauth_email text;

create unique index if not exists idx_users_supabase_auth_user_id
  on public.users(supabase_auth_user_id)
  where supabase_auth_user_id is not null;

create unique index if not exists idx_users_oauth_provider_subject
  on public.users(oauth_provider, oauth_subject)
  where oauth_provider is not null and oauth_subject is not null;

create index if not exists idx_users_oauth_email
  on public.users(oauth_email)
  where oauth_email is not null;
