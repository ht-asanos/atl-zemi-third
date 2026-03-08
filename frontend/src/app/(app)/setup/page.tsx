'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { createProfile } from '@/lib/api/profiles'
import { createGoal } from '@/lib/api/goals'
import { ProfileForm } from '@/components/setup/profile-form'
import { GoalSelector } from '@/components/setup/goal-selector'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { ApiError } from '@/lib/api/client'
import type { CreateProfileRequest } from '@/types/profile'
import type { GoalType } from '@/types/goal'

export default function SetupPage() {
  const { session } = useAuth()
  const router = useRouter()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [profileData, setProfileData] = useState<CreateProfileRequest>({
    age: 25,
    gender: 'male',
    height_cm: 170,
    weight_kg: 65,
    activity_level: 'moderate',
  })
  const [goalType, setGoalType] = useState<GoalType>('diet')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!session?.access_token) return
    setError('')
    setLoading(true)

    try {
      const token = session.access_token

      // Create profile (skip if 409)
      try {
        await createProfile(token, profileData)
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 409)) throw err
      }

      // Create goal
      await createGoal(token, { goal_type: goalType })

      router.push('/staple')
    } catch {
      setError('設定の保存に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-6 text-3xl font-bold">初期設定</h1>
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>プロフィール</CardTitle>
          </CardHeader>
          <CardContent>
            <ProfileForm data={profileData} onChange={setProfileData} />
          </CardContent>
        </Card>

        <Separator />

        <Card>
          <CardHeader>
            <CardTitle>目標を選択</CardTitle>
          </CardHeader>
          <CardContent>
            <GoalSelector value={goalType} onChange={setGoalType} />
          </CardContent>
        </Card>

        <Button type="submit" size="lg" className="w-full" disabled={loading}>
          {loading ? '保存中...' : '次へ: 主食を選ぶ'}
        </Button>
      </form>
    </div>
  )
}
