create table user_recipe_favorites (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    recipe_id uuid not null references recipes(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique (user_id, recipe_id)
);
create index idx_user_recipe_favorites_user on user_recipe_favorites(user_id);
alter table user_recipe_favorites enable row level security;
create policy "users_manage_own_favorites" on user_recipe_favorites
    for all using (auth.uid() = user_id);
