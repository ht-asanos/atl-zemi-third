-- 買い物リストのチェック状態（候補グループ単位）

create table if not exists shopping_list_checks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  start_date date not null,
  group_id text not null,
  checked boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, start_date, group_id)
);

create index if not exists idx_shopping_list_checks_user_start
  on shopping_list_checks(user_id, start_date);

alter table shopping_list_checks enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'shopping_list_checks' and policyname = 'Users can view own shopping_list_checks'
  ) then
    create policy "Users can view own shopping_list_checks"
      on shopping_list_checks for select using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'shopping_list_checks' and policyname = 'Users can insert own shopping_list_checks'
  ) then
    create policy "Users can insert own shopping_list_checks"
      on shopping_list_checks for insert with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'shopping_list_checks' and policyname = 'Users can update own shopping_list_checks'
  ) then
    create policy "Users can update own shopping_list_checks"
      on shopping_list_checks for update using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'shopping_list_checks' and policyname = 'Users can delete own shopping_list_checks'
  ) then
    create policy "Users can delete own shopping_list_checks"
      on shopping_list_checks for delete using (auth.uid() = user_id);
  end if;
end$$;
