-- Link notifications to reels so reel likes/comments can open the right reel.

alter table public.notifications
  add column if not exists reel_id bigint null references public.reels(id) on delete set null;

create index if not exists idx_notifications_reel
  on public.notifications(reel_id)
  where reel_id is not null;
