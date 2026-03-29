create table feedback_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    plan_id uuid references daily_plans(id) on delete set null,
    domain text not null check (domain in ('meal', 'workout', 'mixed')),
    meal_type text check (meal_type in ('breakfast', 'lunch', 'dinner', 'snack')),
    exercise_id text,
    source_text text not null,
    satisfaction int check (satisfaction between 1 and 5),
    rpe float check (rpe between 1 and 10),
    completed boolean,
    created_at timestamptz not null default now(),
    check (
        (domain = 'meal' and meal_type is not null and exercise_id is null)
        or (domain = 'workout' and exercise_id is not null and meal_type is null)
        or (domain = 'mixed' and meal_type is null and exercise_id is null)
    )
);

create index idx_feedback_events_user_created on feedback_events(user_id, created_at desc);
create index idx_feedback_events_plan on feedback_events(plan_id, created_at desc);

create table feedback_event_tags (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references feedback_events(id) on delete cascade,
    tag text not null,
    tag_source text not null check (tag_source in ('llm', 'rule')),
    created_at timestamptz not null default now()
);

create index idx_feedback_event_tags_event on feedback_event_tags(event_id, created_at);

create table adaptation_events (
    id uuid primary key default gen_random_uuid(),
    feedback_event_id uuid not null references feedback_events(id) on delete cascade,
    plan_revision_id uuid references plan_revisions(id) on delete set null,
    domain text not null check (domain in ('meal', 'workout')),
    target_type text not null check (target_type in ('meal_plan', 'recipe_selection', 'workout_plan')),
    target_ref text,
    before_snapshot jsonb not null default '{}'::jsonb,
    after_snapshot jsonb not null default '{}'::jsonb,
    change_summary_json jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index idx_adaptation_events_feedback_event on adaptation_events(feedback_event_id, created_at);
create index idx_adaptation_events_plan_revision on adaptation_events(plan_revision_id);

alter table feedback_events enable row level security;
create policy "Users can view own feedback_events" on feedback_events for select using (auth.uid() = user_id);
create policy "Users can insert own feedback_events" on feedback_events for insert with check (auth.uid() = user_id);

alter table feedback_event_tags enable row level security;
create policy "Users can view own feedback_event_tags" on feedback_event_tags
    for select using (
        exists (
            select 1 from feedback_events fe
            where fe.id = feedback_event_tags.event_id and fe.user_id = auth.uid()
        )
    );
create policy "Users can insert own feedback_event_tags" on feedback_event_tags
    for insert with check (
        exists (
            select 1 from feedback_events fe
            where fe.id = feedback_event_tags.event_id and fe.user_id = auth.uid()
        )
    );

alter table adaptation_events enable row level security;
create policy "Users can view own adaptation_events" on adaptation_events
    for select using (
        exists (
            select 1 from feedback_events fe
            where fe.id = adaptation_events.feedback_event_id and fe.user_id = auth.uid()
        )
    );
create policy "Users can insert own adaptation_events" on adaptation_events
    for insert with check (
        exists (
            select 1 from feedback_events fe
            where fe.id = adaptation_events.feedback_event_id and fe.user_id = auth.uid()
        )
    );
