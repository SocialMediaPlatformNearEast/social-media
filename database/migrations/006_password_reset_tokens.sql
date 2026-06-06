-- Password reset tokens for normal email login.
-- Stores only token hashes. Raw reset tokens are sent by email and never stored.

create table if not exists public.password_reset_tokens (
  id bigserial primary key,
  user_id bigint not null references public.users(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  used_at timestamptz null,
  created_at timestamptz not null default now()
);

create index if not exists idx_password_reset_tokens_user_created
  on public.password_reset_tokens(user_id, created_at desc);

create index if not exists idx_password_reset_tokens_active
  on public.password_reset_tokens(token_hash, expires_at)
  where used_at is null;
