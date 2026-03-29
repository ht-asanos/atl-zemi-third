create table training_progression_sources (
    id uuid primary key default gen_random_uuid(),
    platform text not null default 'youtube',
    channel_handle text not null,
    channel_id text,
    video_id text not null unique,
    video_title text not null,
    video_url text not null,
    published_at timestamptz,
    title_query text,
    transcript_text text,
    transcript_language text,
    transcript_quality_json jsonb not null default '{}'::jsonb,
    ingest_status text not null default 'fetched',
    raw_extraction_json jsonb,
    created_at timestamptz not null default now()
);

create index idx_training_progression_sources_channel_created
    on training_progression_sources(channel_handle, created_at desc);
create index idx_training_progression_sources_status
    on training_progression_sources(ingest_status, created_at desc);

create table training_exercise_aliases (
    id uuid primary key default gen_random_uuid(),
    alias text not null,
    normalized_alias text not null,
    exercise_id text not null,
    goal_scope text[] not null default array['bouldering', 'strength'],
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    unique(normalized_alias, exercise_id)
);

create index idx_training_exercise_aliases_normalized
    on training_exercise_aliases(normalized_alias)
    where is_active = true;

create table training_progression_edges (
    id uuid primary key default gen_random_uuid(),
    source_id uuid not null references training_progression_sources(id) on delete cascade,
    from_label_raw text not null,
    from_exercise_id text,
    from_reps integer not null,
    to_label_raw text not null,
    to_exercise_id text,
    to_reps integer not null,
    relation_type text not null default 'unlock_if_can_do',
    goal_scope text[] not null default array['bouldering', 'strength'],
    evidence_text text,
    confidence double precision not null default 0.0,
    review_status text not null default 'pending',
    review_note text,
    reviewed_by uuid,
    reviewed_at timestamptz,
    created_at timestamptz not null default now()
);

create index idx_training_progression_edges_source
    on training_progression_edges(source_id, created_at);
create index idx_training_progression_edges_review
    on training_progression_edges(review_status, created_at desc);

alter table training_progression_sources enable row level security;
alter table training_exercise_aliases enable row level security;
alter table training_progression_edges enable row level security;

create policy "Authenticated can read active training aliases" on training_exercise_aliases
    for select
    using (auth.role() = 'authenticated' and is_active = true);

create policy "Authenticated can read approved training progression edges" on training_progression_edges
    for select
    using (auth.role() = 'authenticated' and review_status = 'approved');
