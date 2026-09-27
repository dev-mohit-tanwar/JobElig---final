-- JobEligAI initial Supabase schema.
-- Run this migration in the Supabase SQL editor or through the Supabase CLI.

create extension if not exists "pgcrypto";

create table if not exists public.candidate_profiles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users(id) on delete cascade,
    full_name text,
    date_of_birth date,
    category text,
    degree text,
    branch text,
    percentage numeric(5, 2),
    cgpa numeric(4, 2),
    graduation_year integer,
    experience_years numeric(5, 2),
    certifications text[] not null default '{}',
    nationality text,
    additional_information jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint candidate_profiles_percentage_check
        check (percentage is null or percentage between 0 and 100),
    constraint candidate_profiles_cgpa_check
        check (cgpa is null or cgpa between 0 and 10),
    constraint candidate_profiles_experience_check
        check (experience_years is null or experience_years >= 0)
);

create table if not exists public.job_notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    title text,
    organization text,
    original_filename text not null,
    storage_path text not null unique,
    file_size integer not null,
    mime_type text not null default 'application/pdf',
    processing_status text not null default 'UPLOADED',
    page_count integer,
    ocr_text text,
    summary jsonb,
    processing_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint job_notifications_status_check
        check (processing_status in (
            'UPLOADED', 'PROCESSING', 'OCR_COMPLETED',
            'EXTRACTION_COMPLETED', 'COMPLETED', 'FAILED'
        )),
    constraint job_notifications_file_size_check
        check (file_size > 0 and file_size <= 15728640),
    constraint job_notifications_pdf_check
        check (mime_type = 'application/pdf')
);

create table if not exists public.extracted_eligibility (
    id uuid primary key default gen_random_uuid(),
    job_id uuid not null references public.job_notifications(id) on delete cascade,
    version integer not null default 1,
    eligibility_json jsonb not null,
    extraction_status text not null default 'COMPLETED',
    created_at timestamptz not null default now(),
    constraint extracted_eligibility_version_check check (version > 0),
    constraint extracted_eligibility_status_check
        check (extraction_status in ('PROCESSING', 'COMPLETED', 'FAILED')),
    unique (job_id, version)
);

create table if not exists public.eligibility_results (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_id uuid not null references public.job_notifications(id) on delete cascade,
    candidate_profile_id uuid not null references public.candidate_profiles(id) on delete cascade,
    overall_status text not null,
    missing_information text[] not null default '{}',
    warnings text[] not null default '{}',
    final_explanation text,
    matching_json jsonb,
    created_at timestamptz not null default now(),
    constraint eligibility_results_status_check
        check (overall_status in ('ELIGIBLE', 'NOT_ELIGIBLE', 'NEEDS_VERIFICATION'))
);

create table if not exists public.criterion_results (
    id uuid primary key default gen_random_uuid(),
    eligibility_result_id uuid not null references public.eligibility_results(id) on delete cascade,
    criterion_name text not null,
    status text not null,
    candidate_value text,
    required_value text,
    explanation text,
    source_reference text,
    checking_method text not null default 'GEMINI',
    display_order integer not null default 0,
    created_at timestamptz not null default now(),
    constraint criterion_results_status_check
        check (status in ('PASS', 'FAIL', 'NEEDS_VERIFICATION', 'NOT_APPLICABLE')),
    constraint criterion_results_method_check
        check (checking_method in ('DETERMINISTIC', 'GEMINI', 'BOTH'))
);

create index if not exists idx_candidate_profiles_user_id
    on public.candidate_profiles(user_id);
create index if not exists idx_job_notifications_user_id
    on public.job_notifications(user_id);
create index if not exists idx_job_notifications_processing_status
    on public.job_notifications(processing_status);
create index if not exists idx_extracted_eligibility_job_id
    on public.extracted_eligibility(job_id);
create index if not exists idx_eligibility_results_user_id
    on public.eligibility_results(user_id);
create index if not exists idx_eligibility_results_job_id
    on public.eligibility_results(job_id);
create index if not exists idx_criterion_results_result_id
    on public.criterion_results(eligibility_result_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_candidate_profiles_updated_at
    on public.candidate_profiles;
create trigger set_candidate_profiles_updated_at
    before update on public.candidate_profiles
    for each row execute function public.set_updated_at();

drop trigger if exists set_job_notifications_updated_at
    on public.job_notifications;
create trigger set_job_notifications_updated_at
    before update on public.job_notifications
    for each row execute function public.set_updated_at();

alter table public.candidate_profiles enable row level security;
alter table public.job_notifications enable row level security;
alter table public.extracted_eligibility enable row level security;
alter table public.eligibility_results enable row level security;
alter table public.criterion_results enable row level security;

drop policy if exists "Users manage their own candidate profile"
    on public.candidate_profiles;
drop policy if exists "Users manage their own job notifications"
    on public.job_notifications;
drop policy if exists "Users read eligibility for their own jobs"
    on public.extracted_eligibility;
drop policy if exists "Users read their own eligibility results"
    on public.eligibility_results;
drop policy if exists "Users read criteria for their own results"
    on public.criterion_results;

create policy "Users manage their own candidate profile"
    on public.candidate_profiles for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Users manage their own job notifications"
    on public.job_notifications for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Users read eligibility for their own jobs"
    on public.extracted_eligibility for select
    using (exists (
        select 1
        from public.job_notifications jobs
        where jobs.id = extracted_eligibility.job_id
          and jobs.user_id = auth.uid()
    ));

create policy "Users read their own eligibility results"
    on public.eligibility_results for select
    using (auth.uid() = user_id);

create policy "Users read criteria for their own results"
    on public.criterion_results for select
    using (exists (
        select 1
        from public.eligibility_results results
        where results.id = criterion_results.eligibility_result_id
          and results.user_id = auth.uid()
    ));

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'recruitment-pdfs',
    'recruitment-pdfs',
    false,
    15728640,
    array['application/pdf']::text[]
)
on conflict (id) do update
set public = false,
    file_size_limit = 15728640,
    allowed_mime_types = array['application/pdf']::text[];

drop policy if exists "Users read their recruitment PDFs" on storage.objects;
drop policy if exists "Users upload their recruitment PDFs" on storage.objects;
drop policy if exists "Users update their recruitment PDFs" on storage.objects;
drop policy if exists "Users delete their recruitment PDFs" on storage.objects;

create policy "Users read their recruitment PDFs"
    on storage.objects for select
    using (
        bucket_id = 'recruitment-pdfs'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "Users upload their recruitment PDFs"
    on storage.objects for insert
    with check (
        bucket_id = 'recruitment-pdfs'
        and (storage.foldername(name))[1] = auth.uid()::text
        and lower(storage.extension(name)) = 'pdf'
    );

create policy "Users update their recruitment PDFs"
    on storage.objects for update
    using (
        bucket_id = 'recruitment-pdfs'
        and (storage.foldername(name))[1] = auth.uid()::text
    )
    with check (
        bucket_id = 'recruitment-pdfs'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "Users delete their recruitment PDFs"
    on storage.objects for delete
    using (
        bucket_id = 'recruitment-pdfs'
        and (storage.foldername(name))[1] = auth.uid()::text
    );
