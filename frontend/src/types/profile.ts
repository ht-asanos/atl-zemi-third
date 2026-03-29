export type Gender = 'male' | 'female'

export type ActivityLevel = 'low' | 'moderate_low' | 'moderate' | 'high'

export interface CreateProfileRequest {
  age: number
  gender: Gender
  height_cm: number
  weight_kg: number
  activity_level: ActivityLevel
}

export interface ProfileResponse {
  id: string
  age: number
  gender: Gender
  height_cm: number
  weight_kg: number
  activity_level: ActivityLevel
}

export interface UpdateProfileResponse {
  profile: ProfileResponse
  goal_recalculation_needed: boolean
}

export interface AdminStatusResponse {
  is_admin: boolean
}
