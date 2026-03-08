-- MEXT 食品成分 DB + 楽天レシピキャッシュ

create extension if not exists pg_trgm;

-- MEXT 食品成分データ（100g あたり）
create table mext_foods (
    id uuid primary key default gen_random_uuid(),
    mext_food_id text not null unique,
    name text not null,
    category_code text not null,
    category_name text not null,
    kcal_per_100g float not null default 0,
    protein_g_per_100g float not null default 0,
    fat_g_per_100g float not null default 0,
    carbs_g_per_100g float not null default 0,
    fiber_g_per_100g float,
    sodium_mg_per_100g float,
    calcium_mg_per_100g float,
    iron_mg_per_100g float,
    raw_data jsonb not null default '{}',
    scraped_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);
create index idx_mext_foods_category on mext_foods(category_code);
create index idx_mext_foods_name on mext_foods using gin (name gin_trgm_ops);

-- 楽天レシピキャッシュ
create table recipes (
    id uuid primary key default gen_random_uuid(),
    rakuten_recipe_id bigint unique,
    title text not null,
    description text,
    image_url text,
    recipe_url text not null,
    rakuten_category_id text,
    nutrition_per_serving jsonb,
    servings int not null default 1,
    cost_estimate text,
    cooking_minutes int,
    tags text[] not null default '{}',
    is_nutrition_calculated boolean not null default false,
    fetched_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);
create index idx_recipes_tags on recipes using gin (tags);

-- レシピ食材（MEXT 食品への紐付け）
create table recipe_ingredients (
    id uuid primary key default gen_random_uuid(),
    recipe_id uuid not null references recipes(id) on delete cascade,
    ingredient_name text not null,
    amount_text text,
    amount_g float,
    mext_food_id uuid references mext_foods(id),
    match_confidence float,
    manual_review_needed boolean not null default false,
    created_at timestamptz not null default now()
);
create index idx_recipe_ingredients_recipe on recipe_ingredients(recipe_id);

-- RLS: 認証ユーザー読み取り専用
alter table mext_foods enable row level security;
create policy "read_mext_foods" on mext_foods for select
    using (auth.role() = 'authenticated');

alter table recipes enable row level security;
create policy "read_recipes" on recipes for select
    using (auth.role() = 'authenticated');

alter table recipe_ingredients enable row level security;
create policy "read_recipe_ingredients" on recipe_ingredients for select
    using (auth.role() = 'authenticated');
