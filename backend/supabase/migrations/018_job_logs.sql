create table job_logs (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null,
    job_name text not null,
    attempt integer not null check (attempt >= 1),
    triggered_by text not null check (triggered_by in ('schedule', 'manual')),
    status text not null check (status in ('running', 'success', 'failed')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    summary_json jsonb not null default '{}'::jsonb,
    error_message text,
    created_at timestamptz not null default now()
);

create index idx_job_logs_run_id on job_logs(run_id);
create index idx_job_logs_job_created_at on job_logs(job_name, created_at desc);
create index idx_job_logs_status_created_at on job_logs(status, created_at desc);

alter table job_logs enable row level security;
