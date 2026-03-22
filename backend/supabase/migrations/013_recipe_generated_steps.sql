-- recipes に AI 生成手順を保持する
alter table recipes
    add column if not exists generated_steps jsonb not null default '[]'::jsonb,
    add column if not exists steps_status text not null default 'pending',
    add column if not exists steps_model_version text,
    add column if not exists steps_generated_at timestamptz;

create index if not exists idx_recipes_steps_status on recipes(steps_status);
