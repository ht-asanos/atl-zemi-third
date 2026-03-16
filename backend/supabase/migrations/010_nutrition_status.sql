-- Add nutrition_status column to recipes
ALTER TABLE recipes ADD COLUMN IF NOT EXISTS nutrition_status text DEFAULT 'calculated';

-- Backfill: partial match → estimated
UPDATE recipes SET nutrition_status = 'estimated'
  WHERE is_nutrition_calculated = false AND nutrition_per_serving IS NOT NULL;

-- Backfill: no nutrition data → failed
UPDATE recipes SET nutrition_status = 'failed'
  WHERE nutrition_per_serving IS NULL;
