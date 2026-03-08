'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { ProfileForm } from '@/components/setup/profile-form'
import { Button } from '@/components/ui/button'
import { getMyProfile, updateProfile } from '@/lib/api/profiles'
import type { CreateProfileRequest } from '@/types/profile'

export default function SettingsProfilePage() {
  const { session } = useAuth()
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showRecalcDialog, setShowRecalcDialog] = useState(false)
  const [formData, setFormData] = useState<CreateProfileRequest>({
    age: 25,
    gender: 'male',
    height_cm: 170,
    weight_kg: 60,
    activity_level: 'moderate',
  })

  useEffect(() => {
    if (!session?.access_token) return
    getMyProfile(session.access_token)
      .then((profile) => {
        if (profile) {
          setFormData({
            age: profile.age,
            gender: profile.gender,
            height_cm: profile.height_cm,
            weight_kg: profile.weight_kg,
            activity_level: profile.activity_level,
          })
        }
      })
      .catch(() => setError('プロフィールの取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [session?.access_token])

  const handleSave = async () => {
    if (!session?.access_token) return
    setError('')
    setSuccess('')
    setSaving(true)
    try {
      const result = await updateProfile(session.access_token, formData)
      if (result.goal_recalculation_needed) {
        setShowRecalcDialog(true)
      } else {
        setSuccess('プロフィールを更新しました')
      }
    } catch {
      setError('プロフィールの更新に失敗しました')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">読み込み中...</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="mb-6 text-2xl font-bold">プロフィール編集</h1>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}
      {success && (
        <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700">{success}</div>
      )}

      <ProfileForm data={formData} onChange={setFormData} />

      <Button className="mt-6 w-full" onClick={handleSave} disabled={saving}>
        {saving ? '保存中...' : '保存'}
      </Button>

      {showRecalcDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 max-w-sm rounded-lg bg-background p-6 shadow-lg">
            <h2 className="mb-2 text-lg font-semibold">目標を再計算しますか？</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              身長・体重・活動レベルが変更されました。目標のPFCバランスを再計算することをおすすめします。
            </p>
            <div className="flex gap-2">
              <Button
                className="flex-1"
                onClick={() => {
                  setShowRecalcDialog(false)
                  router.push('/settings/goal')
                }}
              >
                はい
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setShowRecalcDialog(false)
                  setSuccess('プロフィールを更新しました')
                }}
              >
                いいえ
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
