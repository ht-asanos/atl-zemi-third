'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { getWeeklyPlans, getShoppingList, patchMeal, patchRecipe, createWeeklyPlan } from '@/lib/api/plans'
import { getStapleFoods } from '@/lib/api/foods'
import { getFavorites, addFavorite, removeFavorite } from '@/lib/api/recipes'
import { WeeklyPlanView } from '@/components/plans/weekly-plan-view'
import { ShoppingList } from '@/components/plans/shopping-list'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api/client'
import type { DailyPlanResponse, ShoppingListResponse } from '@/types/plan'
import type { FoodItem } from '@/types/food'

function getCurrentMonday(): string {
  const now = new Date()
  const utcDay = now.getUTCDay()
  const daysUntilMonday = utcDay === 0 ? 1 : utcDay === 1 ? 0 : 8 - utcDay
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + daysUntilMonday))
  return next.toISOString().slice(0, 10)
}

export default function PlansContent() {
  const { session } = useAuth()
  const router = useRouter()
  const [plans, setPlans] = useState<DailyPlanResponse[]>([])
  const [staples, setStaples] = useState<FoodItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'plan' | 'shopping'>('plan')
  const [shoppingList, setShoppingList] = useState<ShoppingListResponse | null>(null)
  const [shoppingLoading, setShoppingLoading] = useState(false)
  const [favoriteRecipeIds, setFavoriteRecipeIds] = useState<Set<string>>(new Set())
  const [regenerating, setRegenerating] = useState(false)
  const [showRegenerateDialog, setShowRegenerateDialog] = useState(false)

  const isRecipeMode = plans.some((p) => p.meal_plan.some((m) => m.meal_type != null))
  const hasRecipeIds = plans.some((p) =>
    p.meal_plan.some((m) => m.meal_type === 'dinner' && m.recipe?.id)
  )

  useEffect(() => {
    if (!session?.access_token) return

    const token = session.access_token
    const startDate = getCurrentMonday()

    Promise.all([
      getWeeklyPlans(token, startDate),
      getStapleFoods(token),
      getFavorites(token),
    ])
      .then(([weeklyRes, staplesRes, favRes]) => {
        if (weeklyRes.plans.length === 0) {
          router.push('/staple')
          return
        }
        setPlans(weeklyRes.plans)
        setStaples(staplesRes)
        setFavoriteRecipeIds(new Set(favRes.map((f) => f.recipe_id)))
      })
      .catch(() => setError('データの取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [session?.access_token, router])

  const handlePatchMeal = async (planId: string, stapleName: string) => {
    if (!session?.access_token) return
    const updated = await patchMeal(session.access_token, planId, { staple_name: stapleName })
    setPlans((prev) => prev.map((p) => (p.id === planId ? updated : p)))
  }

  const handlePatchRecipe = useCallback(async (planId: string) => {
    if (!session?.access_token) return
    try {
      const updated = await patchRecipe(session.access_token, planId)
      setPlans((prev) => prev.map((p) => (p.id === planId ? updated : p)))
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const startDate = getCurrentMonday()
        const weeklyRes = await getWeeklyPlans(session.access_token, startDate)
        setPlans(weeklyRes.plans)
        setError('プランが更新されました。もう一度お試しください。')
      } else {
        setError('レシピの変更に失敗しました')
      }
    }
  }, [session?.access_token])

  const handleToggleFavorite = useCallback(async (recipeId: string) => {
    if (!session?.access_token) return
    try {
      if (favoriteRecipeIds.has(recipeId)) {
        await removeFavorite(session.access_token, recipeId)
        setFavoriteRecipeIds((prev) => {
          const next = new Set(prev)
          next.delete(recipeId)
          return next
        })
      } else {
        await addFavorite(session.access_token, recipeId)
        setFavoriteRecipeIds((prev) => new Set(prev).add(recipeId))
      }
    } catch {
      setError('お気に入りの更新に失敗しました')
    }
  }, [session?.access_token, favoriteRecipeIds])

  const handleShowShoppingList = async () => {
    setActiveTab('shopping')
    if (shoppingList) return
    if (!session?.access_token) return
    setShoppingLoading(true)
    try {
      const data = await getShoppingList(session.access_token, getCurrentMonday())
      setShoppingList(data)
    } catch {
      setError('買い物リストの取得に失敗しました')
    } finally {
      setShoppingLoading(false)
    }
  }

  const handleRegenerate = async () => {
    if (!session?.access_token) return
    setShowRegenerateDialog(false)
    setRegenerating(true)
    setError('')

    // plan_meta からモード・主食を復元
    const meta = plans[0]?.plan_meta
    const mode = meta?.mode || (isRecipeMode ? 'recipe' : 'classic')
    const stapleName = meta?.staple_name || undefined

    try {
      const result = await createWeeklyPlan(session.access_token, {
        start_date: getCurrentMonday(),
        mode: mode as 'classic' | 'recipe',
        staple_name: stapleName,
      })
      setPlans(result.plans)
      setShoppingList(null)
    } catch {
      setError('プランの再生成に失敗しました')
    } finally {
      setRegenerating(false)
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
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">週間メニュー</h1>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowRegenerateDialog(true)}
          disabled={regenerating}
        >
          {regenerating ? '再生成中...' : 'プランを再生成'}
        </Button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {isRecipeMode && (
        <div className="mb-4 flex gap-2">
          <Button
            variant={activeTab === 'plan' ? 'default' : 'outline'}
            onClick={() => setActiveTab('plan')}
          >
            週間プラン
          </Button>
          <Button
            variant={activeTab === 'shopping' ? 'default' : 'outline'}
            onClick={handleShowShoppingList}
          >
            買い物リスト
          </Button>
        </div>
      )}

      {activeTab === 'plan' ? (
        <WeeklyPlanView
          plans={plans}
          staples={staples}
          onPatchMeal={handlePatchMeal}
          onChangeRecipe={handlePatchRecipe}
          onToggleFavorite={handleToggleFavorite}
          favoriteRecipeIds={favoriteRecipeIds}
        />
      ) : (
        <ShoppingList
          data={shoppingList}
          loading={shoppingLoading}
          noRecipeIds={!hasRecipeIds}
        />
      )}

      {showRegenerateDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 max-w-sm rounded-lg bg-background p-6 shadow-lg">
            <h2 className="mb-2 text-lg font-semibold">プランを再生成</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              現在のプランを上書きしますか？この操作は元に戻せません。
            </p>
            <div className="flex gap-2">
              <Button className="flex-1" onClick={handleRegenerate}>
                再生成する
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowRegenerateDialog(false)}
              >
                キャンセル
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
