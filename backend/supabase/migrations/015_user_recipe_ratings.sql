create table user_recipe_ratings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    recipe_id uuid not null references recipes(id) on delete cascade,
    rating smallint not null check (rating in (-1, 1)),
    -- rating: -1=dislike, 1=like（0は DELETE で未評価に戻す）
    -- 将来拡張メモ: updated_at を使った半減期スコア（例: score = rating * 0.5^(days/90)）
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, recipe_id)
);
create index idx_user_recipe_ratings_user on user_recipe_ratings(user_id);
alter table user_recipe_ratings enable row level security;

-- RLS: 操作別の明示ポリシー
create policy "ratings_select_own" on user_recipe_ratings
    for select using (auth.uid() = user_id);
create policy "ratings_insert_own" on user_recipe_ratings
    for insert with check (auth.uid() = user_id);
create policy "ratings_update_own" on user_recipe_ratings
    for update using (auth.uid() = user_id);
create policy "ratings_delete_own" on user_recipe_ratings
    for delete using (auth.uid() = user_id);
