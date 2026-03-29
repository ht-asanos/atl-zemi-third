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
  recipe_filters?: RecipeFilters
  available_equipment?: TrainingEquipment[]
}

export interface PatchMealRequest {
  staple_name: string
}

export interface PatchRecipeRequest {
  recipe_filters?: RecipeFilters
}

export interface RecipeFilters {
  allowed_sources: Array<'rakuten' | 'youtube'>
  prefer_favorites: boolean
  exclude_disliked: boolean
  prefer_variety: boolean
}

export interface PlanMeta {
  mode: string | null
  staple_name: string | null
  recipe_filters?: RecipeFilters | null
  available_equipment?: TrainingEquipment[] | null
  training_recommendations?: TrainingRecommendation[] | null
  validation?: Record<string, unknown> | null
  validation_issues?: string[] | null
  duplicate_count?: number | null
  candidate_pool_size?: number | null
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
  youtube_video_id?: string | null
  recipe_source?: 'rakuten' | 'youtube' | string
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
  required_equipment?: TrainingEquipment[]
}

export type TrainingEquipment = 'none' | 'pull_up_bar' | 'dip_bars' | 'dumbbells'

export interface TrainingRecommendation {
  from_exercise_id: string
  to_exercise_id: string
  reason: string
}

export interface TrainingSkillTreeNode {
  exercise_id: string
  name_ja: string
  required_equipment: TrainingEquipment[] | string[]
  best_completed_reps: number
  status: 'locked' | 'unlocked' | 'current' | 'recommended' | 'mastered' | 'blocked'
  next_threshold_reps?: number | null
  recommendation_reason?: string | null
  latest_log_summary?: {
    log_date: string
    sets: number
    reps: number
    rpe?: number | null
    completed: boolean
  } | null
  latest_feedback_summary?: {
    created_at: string
    source_text: string
    tags: string[]
  } | null
}

export interface TrainingSkillTreeEdge {
  from_exercise_id: string
  to_exercise_id: string
  from_reps_required: number
  to_reps_target: number
  is_recommended_path: boolean
}

export interface TrainingSkillTreeTrack {
  track_id: string
  title: string
  nodes: TrainingSkillTreeNode[]
  edges: TrainingSkillTreeEdge[]
}

export interface TrainingSkillTreeSummary {
  goal_type: string
  available_edge_count: number
  recommended_count: number
  has_negative_feedback: boolean
}

export interface TrainingSkillTreeResponse {
  summary: TrainingSkillTreeSummary
  tracks: TrainingSkillTreeTrack[]
}
