-- 016_nutrition_matching_improvements.sql
-- trigram 類似度検索 RPC と negligible フラグの追加

-- 1. similarity_search RPC（既存環境は CREATE OR REPLACE で上書き）
CREATE OR REPLACE FUNCTION similarity_search_mext_foods(
  search_name text,
  threshold float DEFAULT 0.3
)
RETURNS TABLE(id uuid, name text, similarity float)
LANGUAGE sql STABLE
AS $$
  SELECT id, name, similarity(name, search_name) AS similarity
  FROM mext_foods
  WHERE similarity(name, search_name) >= threshold
  ORDER BY similarity DESC
  LIMIT 5;
$$;

COMMENT ON FUNCTION similarity_search_mext_foods IS
  'trigram 類似度で mext_foods を検索する。ingredient_matcher.py から呼び出し。';

-- 2. recipe_ingredients に is_negligible カラム追加
ALTER TABLE recipe_ingredients
  ADD COLUMN IF NOT EXISTS is_negligible boolean NOT NULL DEFAULT false;
