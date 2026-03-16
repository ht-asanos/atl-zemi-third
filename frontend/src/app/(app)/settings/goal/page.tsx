'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/providers/auth-provider'
import { GoalSelector } from '@/components/setup/goal-selector'
import { Button } from '@/components/ui/button'
import { Spinner, InlineSpinner } from '@/components/ui/spinner'
import { toast } from 'sonner'
import { getMyGoal, createGoal } from '@/lib/api/goals'
import type { GoalType } from '@/types/goal'

export default function SettingsGoalPage() {
  const { session } = useAuth()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [goalType, setGoalType] = useState<GoalType>('diet')

  useEffect(() => {
    if (!session?.access_token) return
    getMyGoal(session.access_token)
      .then((goal) => {
        if (goal) {
          setGoalType(goal.goal_type)
        }
      })
      .catch(() => setError('目標の取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [session?.access_token])

  const handleSave = async () => {
    if (!session?.access_token) return
    setError('')
    setSuccess('')
    setSaving(true)
    try {
      const result = await createGoal(session.access_token, { goal_type: goalType })
      const msg = `目標を更新しました（${result.target_kcal} kcal / P: ${result.protein_g}g / F: ${result.fat_g}g / C: ${result.carbs_g}g）`
      toast.success(msg)
      setSuccess('更新済み')
    } catch {
      setError('目標の更新に失敗しました')
      toast.error('目標の更新に失敗しました')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner />
        <p className="ml-2 text-muted-foreground">読み込み中...</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-6 text-2xl font-bold">目標変更</h1>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      <GoalSelector value={goalType} onChange={setGoalType} />

      <Button className="mt-6 w-full" onClick={handleSave} disabled={saving}>
        {saving ? <><InlineSpinner /> 保存中...</> : '目標を保存'}
      </Button>
      {success && (
        <p className="mt-2 text-center text-sm text-green-600">{success}</p>
      )}
    </div>
  )
}
