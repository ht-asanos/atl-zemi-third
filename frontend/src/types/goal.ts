export type GoalType = 'diet' | 'strength' | 'bouldering'

export interface CreateGoalRequest {
  goal_type: GoalType
}

export interface GoalResponse {
  id: string
  goal_type: GoalType
  target_kcal: number
  protein_g: number
  fat_g: number
  carbs_g: number
}
