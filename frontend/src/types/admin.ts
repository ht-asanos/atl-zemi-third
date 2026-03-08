export interface ReviewIngredientItem {
  id: string
  recipe_id: string
  recipe_title: string
  ingredient_name: string
  amount_text: string | null
  current_mext_food_id: string | null
  current_mext_food_name: string | null
  match_confidence: number | null
  manual_review_needed: boolean
  is_nutrition_calculated: boolean
}

export interface ReviewListResponse {
  items: ReviewIngredientItem[]
  total: number
  page: number
  per_page: number
}

export interface ReviewUpdateRequest {
  mext_food_id: string | null
  approved: boolean
}

export interface MextFoodSearchItem {
  id: string
  mext_food_id: string
  name: string
  category_name: string
  kcal_per_100g: number
  protein_g_per_100g: number
}

export interface MextFoodSearchResponse {
  items: MextFoodSearchItem[]
}
