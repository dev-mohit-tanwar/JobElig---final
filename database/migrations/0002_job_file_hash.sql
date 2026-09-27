alter table public.job_notifications
    add column if not exists file_hash text;

create unique index if not exists idx_job_notifications_user_file_hash
    on public.job_notifications(user_id, file_hash)
    where file_hash is not null;
