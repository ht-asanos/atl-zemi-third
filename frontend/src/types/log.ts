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
  domain?: 'meal' | 'workout' | 'mixed'
  meal_type?: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  exercise_id?: string
  satisfaction?: number | null
  rpe?: number | null
  completed?: boolean | null
}

export interface FeedbackTagResponse {
  id: string
  tag: string
  source_text: string
  created_at: string
}

export interface FeedbackEventTagResponse {
  id: string
  event_id: string
  tag: string
  tag_source: 'llm' | 'rule'
  created_at: string
}

export interface AdaptationEventResponse {
  id: string
  feedback_event_id: string
  plan_revision_id: string | null
  domain: 'meal' | 'workout'
  target_type: 'meal_plan' | 'recipe_selection' | 'workout_plan'
  target_ref: string | null
  before_snapshot: unknown
  after_snapshot: unknown
  change_summary_json: string[]
  created_at: string
}

export interface FeedbackEventResponse {
  id: string
  plan_id: string | null
  domain: 'meal' | 'workout' | 'mixed'
  meal_type?: 'breakfast' | 'lunch' | 'dinner' | 'snack' | null
  exercise_id?: string | null
  source_text: string
  satisfaction?: number | null
  rpe?: number | null
  completed?: boolean | null
  created_at: string
}

export interface FeedbackEventDetailResponse extends FeedbackEventResponse {
  tags: FeedbackEventTagResponse[]
  adaptation_events: AdaptationEventResponse[]
}

export interface AdaptationResponse {
  feedback_event_id?: string | null
  adaptation_event_ids?: string[]
  tags_applied: string[]
  changes_summary: string[]
  extraction_status: 'success' | 'partial' | 'failed'
  new_plan: import('@/types/plan').DailyPlanResponse | null
}
