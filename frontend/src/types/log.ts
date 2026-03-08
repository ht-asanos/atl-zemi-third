export interface CreateMealLogRequest {
  plan_id: string
  log_date: string
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  completed: boolean
  satisfaction?: number | null
}

export interface MealLogResponse {
  id: string
  plan_id: string
  log_date: string
  meal_type: string
  completed: boolean
  satisfaction: number | null
  created_at: string
}

export interface CreateWorkoutLogRequest {
  plan_id: string
  log_date: string
  exercise_id: string
  sets: number
  reps: number
  rpe?: number | null
  completed: boolean
}

export interface WorkoutLogResponse {
  id: string
  plan_id: string
  log_date: string
  exercise_id: string
  sets: number
  reps: number
  rpe: number | null
  completed: boolean
  created_at: string
}

export interface CreateFeedbackRequest {
  plan_id: string
  source_text: string
}

export interface FeedbackTagResponse {
  id: string
  tag: string
  source_text: string
  created_at: string
}

export interface AdaptationResponse {
  tags_applied: string[]
  changes_summary: string[]
  extraction_status: 'success' | 'partial' | 'failed'
  new_plan: import('@/types/plan').DailyPlanResponse | null
}
