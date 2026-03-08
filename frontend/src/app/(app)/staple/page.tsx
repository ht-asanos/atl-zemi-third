'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { getStapleFoods } from '@/lib/api/foods'
import { createWeeklyPlan } from '@/lib/api/plans'
import { StapleCard } from '@/components/staple/staple-card'
import { Button } from '@/components/ui/button'
import type { FoodItem } from '@/types/food'

function getNextMonday(): string {
  const now = new Date()
  const utcDay = now.getUTCDay()
  // 0=Sun, 1=Mon, ..., 6=Sat
  const daysUntilMonday = utcDay === 0 ? 1 : utcDay === 1 ? 0 : 8 - utcDay
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + daysUntilMonday))
  return next.toISOString().slice(0, 10)
}

type PlanMode = 'recipe' | 'classic'

export default function StaplePage() {
  const { session } = useAuth()
  const router = useRouter()
  const [foods, setFoods] = useState<FoodItem[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<PlanMode>('recipe')

  useEffect(() => {
    if (!session?.access_token) return
    getStapleFoods(session.access_token).then(setFoods).catch(() => setError('主食一覧の取得に失敗しました'))
  }, [session?.access_token])

  const handleGenerate = async () => {
    if (!session?.access_token) return
    if (mode === 'classic' && !selected) return
    setError('')
    setLoading(true)

    try {
      await createWeeklyPlan(session.access_token, {
        start_date: getNextMonday(),
        mode,
        staple_name: selected || undefined,
      })
      router.push('/plans')
    } catch {
      setError('プラン生成に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-2 text-3xl font-bold">プランを生成</h1>
      <p className="mb-6 text-muted-foreground">モードを選んでプランを作成しましょう</p>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="mb-6 flex gap-2">
        <Button
          variant={mode === 'recipe' ? 'default' : 'outline'}
          onClick={() => { setMode('recipe'); setSelected(null) }}
        >
          レシピモード
        </Button>
        <Button
          variant={mode === 'classic' ? 'default' : 'outline'}
          onClick={() => { setMode('classic'); setSelected(null) }}
        >
          主食モード
        </Button>
      </div>

      {mode === 'recipe' ? (
        <div className="mb-6 space-y-4">
          <div className="rounded-md border p-4 space-y-2">
            <p className="font-medium">レシピモード</p>
            <p className="text-sm text-muted-foreground">
              朝食（ヨーグルト/納豆）+ 昼食（おにぎり）+ 夕食（日替わりレシピ）の構成で7日分を自動生成します。
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            夕食レシピのベースとなる主食を選んでください（任意）
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {foods.map((food) => (
              <StapleCard
                key={food.name}
                food={food}
                selected={selected === food.name}
                onSelect={() => setSelected((prev) => prev === food.name ? null : food.name)}
              />
            ))}
          </div>
        </div>
      ) : (
        <>
          <p className="mb-4 text-muted-foreground">1週間のベースとなる主食を選んでください</p>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {foods.map((food) => (
              <StapleCard
                key={food.name}
                food={food}
                selected={selected === food.name}
                onSelect={() => setSelected(food.name)}
              />
            ))}
          </div>
        </>
      )}

      <Button
        size="lg"
        className="w-full"
        disabled={(mode === 'classic' && !selected) || loading}
        onClick={handleGenerate}
      >
        {loading ? '生成中...' : 'プランを生成'}
      </Button>
    </div>
  )
}
