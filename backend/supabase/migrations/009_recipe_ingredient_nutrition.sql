-- recipe_ingredients に食材ごとの計算済み栄養を保持する
alter table recipe_ingredients
    add column if not exists kcal float,
    add column if not exists protein_g float,
    add column if not exists fat_g float,
    add column if not exists carbs_g float;

create index if not exists idx_recipe_ingredients_recipe_id on recipe_ingredients(recipe_id);
