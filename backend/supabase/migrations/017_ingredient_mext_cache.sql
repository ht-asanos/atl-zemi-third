-- ingredient_mext_cache: 食材名 → MEXT 食品 ID のマッチングキャッシュ
-- trigram / Gemini マッチング結果を永続化し、再計算コストを削減する。
-- no_match エントリは TTL 7 日（expires_at）で自動失効。

CREATE TABLE IF NOT EXISTS ingredient_mext_cache (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_name text NOT NULL UNIQUE,
    mext_food_id uuid REFERENCES mext_foods(id) ON DELETE CASCADE,
    confidence float NOT NULL,
    source text NOT NULL CHECK (source IN ('trigram', 'gemini', 'no_match')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz  -- NULL = 無期限。no_match のみ 7 日後をセット
);

CREATE INDEX idx_ingredient_mext_cache_name ON ingredient_mext_cache(normalized_name);
