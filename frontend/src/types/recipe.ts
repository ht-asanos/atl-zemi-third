export interface RecipeIngredientDetail {
  ingredient_name: string
  display_ingredient_name?: string | null
  alternative_ingredient_names?: string[]
  amount_text: string | null
  amount_g: number | null
  kcal: number | null
  protein_g: number | null
  fat_g: number | null
  carbs_g: number | null
  matched_food_name?: string | null
  nutrition_match_status?: 'matched' | 'estimated' | 'unmatched'
  nutrition_source?: 'mext' | 'fallback' | 'none'
}

export interface RecipeStep {
  step_no: number
  text: string
  est_minutes: number | null
}

export interface RecipeDetail {
  id: string
  title: string
  description: string | null
  image_url: string | null
  recipe_url: string
  nutrition_per_serving: {
    kcal: number
    protein_g: number
    fat_g: number
    carbs_g: number
  } | null
  servings: number
  cooking_minutes: number | null
  cost_estimate: string | null
  tags: string[]
  ingredients: RecipeIngredientDetail[]
  ingredient_nutrition_coverage?: {
    matched_count: number
    total_count: number
    coverage_rate: number
  } | null
  generated_steps?: RecipeStep[]
  steps_status?: 'pending' | 'generated' | 'failed'
  youtube_video_id?: string | null
  recipe_source?: 'rakuten' | 'youtube' | string
}
