import { apiClient, ApiError } from './client'
import type { AdminStatusResponse, CreateProfileRequest, ProfileResponse, UpdateProfileResponse } from '@/types/profile'

export async function createProfile(
  token: string,
  data: CreateProfileRequest
): Promise<ProfileResponse> {
  return apiClient<ProfileResponse>('/profiles', {
    method: 'POST',
    body: JSON.stringify(data),
  }, token)
}

export async function getMyProfile(
  token: string
): Promise<ProfileResponse | null> {
  try {
    return await apiClient<ProfileResponse>('/profiles/me', {}, token)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

export async function updateProfile(
  token: string,
  data: CreateProfileRequest
): Promise<UpdateProfileResponse> {
  return apiClient<UpdateProfileResponse>('/profiles/me', {
    method: 'PUT',
    body: JSON.stringify(data),
  }, token)
}

export async function getMyAdminStatus(
  token: string
): Promise<AdminStatusResponse> {
  return apiClient<AdminStatusResponse>('/profiles/me/admin-status', {}, token)
}
