-- YouTube 動画 ID（重複判定用）
ALTER TABLE recipes
    ADD COLUMN IF NOT EXISTS youtube_video_id text UNIQUE;

-- レシピソース（CHECK 制約で値を制限）
ALTER TABLE recipes
    ADD COLUMN IF NOT EXISTS recipe_source text NOT NULL DEFAULT 'rakuten';

ALTER TABLE recipes
    ADD CONSTRAINT recipes_source_check
    CHECK (recipe_source IN ('rakuten', 'youtube'));

CREATE INDEX IF NOT EXISTS idx_recipes_youtube_video_id ON recipes(youtube_video_id);
CREATE INDEX IF NOT EXISTS idx_recipes_source ON recipes(recipe_source);
