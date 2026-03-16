export interface ShoppingListItem {
  ingredient_name: string
  group_id?: string | null
  checked?: boolean
  mext_food_id?: string | null
  amount_text?: string | null
  amount_g?: number | null
  category_name?: string | null
  recipe_titles: string[]
  is_purchasable?: boolean
}

export interface ShoppingListResponse {
  start_date: string
  items: ShoppingListItem[]
  recipe_count: number
}

export interface ShoppingListChecksResponse {
  start_date: string
  checked_group_ids: string[]
}

export interface SetShoppingListCheckRequest {
  start_date: string
  group_id: string
  checked: boolean
}

export interface WeeklyPlanRequest {
  start_date: string
  staple_name?: string
  mode?: 'classic' | 'recipe'
}

export interface PatchMealRequest {
  staple_name: string
}

export interface PlanMeta {
  mode: string | null
  staple_name: string | null
}

export interface DailyPlanResponse {
  id: string
  plan_date: string
  meal_plan: MealSuggestion[]
  workout_plan: TrainingDay | Record<string, never>
  plan_meta?: PlanMeta | null
}

export interface WeeklyPlanResponse {
  plans: DailyPlanResponse[]
}

export interface RecipeInPlan {
  id?: string
  title: string
  image_url?: string
  recipe_url: string
  cooking_minutes?: number | null
  nutrition_per_serving?: {
    kcal: number
    protein_g: number
    fat_g: number
    carbs_g: number
  } | null
}

export interface MealSuggestion {
  meal_type?: 'breakfast' | 'lunch' | 'dinner' | null
  staple: FoodItemInPlan
  protein_sources: FoodItemInPlan[]
  bulk_items: FoodItemInPlan[]
  total_kcal: number
  total_protein_g: number
  total_fat_g: number
  total_carbs_g: number
  total_price_yen: number
  total_cooking_minutes: number
  recipe?: RecipeInPlan | null
  nutrition_status?: 'calculated' | 'estimated' | 'failed' | null
  nutrition_warning?: string | null
}

export interface FoodItemInPlan {
  name: string
  category: string
  kcal_per_serving: number
  protein_g: number
  fat_g: number
  carbs_g: number
  serving_unit: string
  price_yen: number
  cooking_minutes: number
}

export interface TrainingDay {
  day_label: string
  exercises: Exercise[]
}

export interface Exercise {
  id: string
  name_ja: string
  muscle_group: string
  sets: number
  reps: number | string
  rest_seconds: number
}
