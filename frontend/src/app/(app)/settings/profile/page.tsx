'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { ProfileForm } from '@/components/setup/profile-form'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Spinner, InlineSpinner } from '@/components/ui/spinner'
import { toast } from 'sonner'
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
        toast.success('プロフィールを更新しました')
        setSuccess('更新済み')
      }
    } catch {
      setError('プロフィールの更新に失敗しました')
      toast.error('プロフィールの更新に失敗しました')
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
    <div className="mx-auto max-w-md p-6">
      <h1 className="mb-6 text-2xl font-bold">プロフィール編集</h1>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      <ProfileForm data={formData} onChange={setFormData} />

      <Button className="mt-6 w-full" onClick={handleSave} disabled={saving}>
        {saving ? <><InlineSpinner /> 保存中...</> : '保存'}
      </Button>
      {success && (
        <p className="mt-2 text-center text-sm text-green-600">{success}</p>
      )}

      <ConfirmDialog
        open={showRecalcDialog}
        title="目標を再計算しますか？"
        description="身長・体重・活動レベルが変更されました。目標のPFCバランスを再計算することをおすすめします。"
        confirmLabel="はい"
        cancelLabel="いいえ"
        onConfirm={() => {
          setShowRecalcDialog(false)
          router.push('/settings/goal')
        }}
        onCancel={() => {
          setShowRecalcDialog(false)
          toast.success('プロフィールを更新しました')
          setSuccess('更新済み')
        }}
      />
    </div>
  )
}
