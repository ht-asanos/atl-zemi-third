-- Phase 1: テーブル定義
-- 実行前提: supabase start && supabase db reset

-- profiles: ユーザー基本情報
create table profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    age int not null check (age between 10 and 120),
    gender text not null check (gender in ('male', 'female')),
    height_cm float not null check (height_cm > 0),
    weight_kg float not null check (weight_kg > 0),
    activity_level text not null check (activity_level in ('low', 'moderate_low', 'moderate', 'high')),
    allergies text[] not null default '{}',
    max_cooking_minutes int not null default 10,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- goals: ユーザー目標
create table goals (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    goal_type text not null check (goal_type in ('diet', 'strength', 'bouldering')),
    target_kcal float not null,
    protein_g float not null,
    fat_g float not null,
    carbs_g float not null,
    created_at timestamptz not null default now()
);
create index idx_goals_user_id on goals(user_id);

-- food_master: 食材マスタ（グローバル、user_id なし）
create table food_master (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    category text not null check (category in ('staple', 'protein', 'bulk')),
    kcal_per_serving float not null,
    protein_g float not null,
    fat_g float not null,
    carbs_g float not null,
    serving_unit text not null,
    price_yen int not null default 0,
    cooking_minutes int not null default 0,
    created_at timestamptz not null default now()
);

-- daily_plans: 日次提案（食事 + 運動を JSONB で保持）
-- Phase 2 では PATCH 時に jsonb_set() による部分更新を使用し、
-- meal_plan と workout_plan を独立に更新する。
create table daily_plans (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    plan_date date not null,
    meal_plan jsonb not null default '{}',
    workout_plan jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, plan_date)
);
create index idx_daily_plans_user_date on daily_plans(user_id, plan_date);

-- meal_logs: 食事実績ログ
create table meal_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    plan_id uuid references daily_plans(id) on delete set null,
    log_date date not null,
    meal_type text not null check (meal_type in ('breakfast', 'lunch', 'dinner', 'snack')),
    completed boolean not null default false,
    satisfaction int check (satisfaction between 1 and 5),
    photo_url text,
    created_at timestamptz not null default now()
);
create index idx_meal_logs_user_date on meal_logs(user_id, log_date);

-- workout_logs: トレーニング実績ログ
create table workout_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    plan_id uuid references daily_plans(id) on delete set null,
    log_date date not null,
    exercise_id text not null,
    sets int not null,
    reps int not null,
    rpe float check (rpe between 1 and 10),
    completed boolean not null default false,
    created_at timestamptz not null default now()
);
create index idx_workout_logs_user_date on workout_logs(user_id, log_date);

-- feedback_tags: NLP 抽出タグ
create table feedback_tags (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    plan_id uuid references daily_plans(id) on delete set null,
    tag text not null check (tag in ('too_hard', 'cannot_complete_reps', 'forearm_sore', 'bored_staple', 'too_much_food')),
    source_text text,
    created_at timestamptz not null default now()
);
create index idx_feedback_tags_user on feedback_tags(user_id);

-- plan_revisions: 再生成差分と理由
create table plan_revisions (
    id uuid primary key default gen_random_uuid(),
    plan_id uuid not null references daily_plans(id) on delete cascade,
    user_id uuid not null references profiles(id) on delete cascade,
    previous_plan jsonb not null,
    new_plan jsonb not null,
    reason text not null,
    created_at timestamptz not null default now()
);
create index idx_plan_revisions_plan on plan_revisions(plan_id);
