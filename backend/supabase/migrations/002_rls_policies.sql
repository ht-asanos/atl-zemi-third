-- Phase 1: Row Level Security ポリシー

-- profiles
alter table profiles enable row level security;
create policy "Users can view own profile" on profiles for select using (auth.uid() = id);
create policy "Users can insert own profile" on profiles for insert with check (auth.uid() = id);
create policy "Users can update own profile" on profiles for update using (auth.uid() = id);

-- goals
alter table goals enable row level security;
create policy "Users can view own goals" on goals for select using (auth.uid() = user_id);
create policy "Users can insert own goals" on goals for insert with check (auth.uid() = user_id);
create policy "Users can update own goals" on goals for update using (auth.uid() = user_id);

-- food_master: 認証済みユーザーに読み取り専用
alter table food_master enable row level security;
create policy "Authenticated users can read food_master" on food_master for select using (auth.role() = 'authenticated');

-- daily_plans
alter table daily_plans enable row level security;
create policy "Users can view own plans" on daily_plans for select using (auth.uid() = user_id);
create policy "Users can insert own plans" on daily_plans for insert with check (auth.uid() = user_id);
create policy "Users can update own plans" on daily_plans for update using (auth.uid() = user_id);

-- meal_logs
alter table meal_logs enable row level security;
create policy "Users can view own meal_logs" on meal_logs for select using (auth.uid() = user_id);
create policy "Users can insert own meal_logs" on meal_logs for insert with check (auth.uid() = user_id);
create policy "Users can update own meal_logs" on meal_logs for update using (auth.uid() = user_id);

-- workout_logs
alter table workout_logs enable row level security;
create policy "Users can view own workout_logs" on workout_logs for select using (auth.uid() = user_id);
create policy "Users can insert own workout_logs" on workout_logs for insert with check (auth.uid() = user_id);
create policy "Users can update own workout_logs" on workout_logs for update using (auth.uid() = user_id);

-- feedback_tags
alter table feedback_tags enable row level security;
create policy "Users can view own feedback_tags" on feedback_tags for select using (auth.uid() = user_id);
create policy "Users can insert own feedback_tags" on feedback_tags for insert with check (auth.uid() = user_id);

-- plan_revisions
alter table plan_revisions enable row level security;
create policy "Users can view own plan_revisions" on plan_revisions for select using (auth.uid() = user_id);
create policy "Users can insert own plan_revisions" on plan_revisions for insert with check (auth.uid() = user_id);
