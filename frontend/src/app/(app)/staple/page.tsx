'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { getStapleFoods } from '@/lib/api/foods'
import { createWeeklyPlan, getWeeklyPlans } from '@/lib/api/plans'
import { StapleCard } from '@/components/staple/staple-card'
import { Button } from '@/components/ui/button'
import { InlineSpinner, Spinner } from '@/components/ui/spinner'
import { StepIndicator } from '@/components/ui/step-indicator'
import { toast } from 'sonner'
import { getNextMondayUTC } from '@/lib/date-utils'
import { getErrorInfo } from '@/lib/errors'
import { ApiError } from '@/lib/api/client'
import { Info } from 'lucide-react'
import type { FoodItem } from '@/types/food'

type PlanMode = 'recipe' | 'classic'

function StapleContent() {
  const { session } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const fromPlans = searchParams.get('from') === 'plans'
  const fromSettings = searchParams.get('from') === 'settings'
  const [foods, setFoods] = useState<FoodItem[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<PlanMode>('recipe')
  const [currentMode, setCurrentMode] = useState<PlanMode | null>(null)
  const [currentStaple, setCurrentStaple] = useState<string | null>(null)

  useEffect(() => {
    if (!session?.access_token) return
    const token = session.access_token
    const startDate = getNextMondayUTC()

    Promise.all([
      getStapleFoods(token),
      getWeeklyPlans(token, startDate).catch(() => null),
    ])
      .then(([foodsRes, weeklyRes]) => {
        setFoods(foodsRes)
        if (!weeklyRes || weeklyRes.plans.length === 0) return
        const meta = weeklyRes.plans[0]?.plan_meta
        const detectedMode = meta?.mode === 'classic' ? 'classic' : 'recipe'
        const detectedStaple = meta?.staple_name ?? null
        setCurrentMode(detectedMode)
        setCurrentStaple(detectedStaple)
        setMode(detectedMode)
        setSelected(detectedStaple)
      })
      .catch(() => setError('主食一覧の取得に失敗しました'))
  }, [session?.access_token])

  const handleGenerate = async () => {
    if (!session?.access_token) return
    if (mode === 'classic' && !selected) return
    setError('')
    setLoading(true)

    try {
      await createWeeklyPlan(session.access_token, {
        start_date: getNextMondayUTC(),
        mode,
        staple_name: selected || undefined,
      })
      router.push('/plans')
    } catch (err) {
      const info = err instanceof ApiError ? getErrorInfo(err.errorCode) : getErrorInfo()
      setError(info.message)
      toast.error(info.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <StepIndicator currentStep={2} />

      {fromPlans && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700">
          <Info className="h-4 w-4 shrink-0" />
          まだプランがありません。モードを選んでプランを作成しましょう
        </div>
      )}
      {fromSettings && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
          <Info className="h-4 w-4 shrink-0" />
          現在の設定を読み込みました。変更する場合は主食またはモードを選び直して保存してください。
        </div>
      )}

      <h1 className="mb-2 text-3xl font-bold">プランを生成</h1>
      <p className="mb-6 text-muted-foreground">モードを選んでプランを作成しましょう</p>
      {(currentMode || currentStaple) && (
        <p className="mb-4 text-sm text-muted-foreground">
          現在設定: {currentMode === 'classic' ? '主食モード' : 'レシピモード'}
          {currentStaple ? ` / 主食: ${currentStaple}` : ''}
        </p>
      )}

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
        {loading ? <><InlineSpinner /> 生成中...</> : 'プランを生成'}
      </Button>
    </div>
  )
}

export default function StaplePage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner />
      </div>
    }>
      <StapleContent />
    </Suspense>
  )
}
