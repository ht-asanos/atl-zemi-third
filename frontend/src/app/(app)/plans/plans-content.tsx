'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import {
  getWeeklyPlans,
  getShoppingList,
  patchMeal,
  patchRecipe,
  createWeeklyPlan,
  getShoppingListChecks,
  setShoppingListCheck,
} from '@/lib/api/plans'
import { getStapleFoods } from '@/lib/api/foods'
import { getMyGoal } from '@/lib/api/goals'
import { getFavorites, addFavorite, removeFavorite, getRecipe } from '@/lib/api/recipes'
import { WeeklyPlanView } from '@/components/plans/weekly-plan-view'
import { RecipeDetailModal } from '@/components/plans/recipe-detail-modal'
import { RecipeRegenerateDialog } from '@/components/plans/recipe-regenerate-dialog'
import { ShoppingList } from '@/components/plans/shopping-list'
import { Button } from '@/components/ui/button'
import { Spinner, InlineSpinner } from '@/components/ui/spinner'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api/client'
import { getErrorInfo } from '@/lib/errors'
import { getNextMondayUTC } from '@/lib/date-utils'
import Link from 'next/link'
import { CalendarX2 } from 'lucide-react'
import type { DailyPlanResponse, RecipeFilters, ShoppingListResponse } from '@/types/plan'
import type { FoodItem } from '@/types/food'
import type { RecipeDetail } from '@/types/recipe'
import type { GoalResponse } from '@/types/goal'

const DEFAULT_RECIPE_FILTERS: RecipeFilters = {
  allowed_sources: ['rakuten', 'youtube'],
  prefer_favorites: true,
  exclude_disliked: true,
  prefer_variety: true,
}

function getWeekStartDate(offset: number): string {
  const base = new Date(getNextMondayUTC() + 'T00:00:00Z')
  base.setUTCDate(base.getUTCDate() + offset * 7)
  return base.toISOString().slice(0, 10)
}

export default function PlansContent() {
  const { session } = useAuth()
  const router = useRouter()
  const [plans, setPlans] = useState<DailyPlanResponse[]>([])
  const [staples, setStaples] = useState<FoodItem[]>([])
  const [goal, setGoal] = useState<GoalResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'plan' | 'shopping'>('plan')
  const [shoppingList, setShoppingList] = useState<ShoppingListResponse | null>(null)
  const [shoppingLoading, setShoppingLoading] = useState(false)
  const [checkedGroupIds, setCheckedGroupIds] = useState<Set<string>>(new Set())
  const [updatingGroupIds, setUpdatingGroupIds] = useState<Set<string>>(new Set())
  const [favoriteRecipeIds, setFavoriteRecipeIds] = useState<Set<string>>(new Set())
  const [regenerating, setRegenerating] = useState(false)
  const [showRegenerateDialog, setShowRegenerateDialog] = useState(false)
  const [pendingRecipePlanId, setPendingRecipePlanId] = useState<string | null>(null)
  const [weekOffset, setWeekOffset] = useState(0)
  const [isEmpty, setIsEmpty] = useState(false)
  const [viewingRecipeId, setViewingRecipeId] = useState<string | null>(null)
  const recipeCacheRef = useRef<Map<string, RecipeDetail>>(new Map())

  const startDate = useMemo(() => getWeekStartDate(weekOffset), [weekOffset])
  const isPastWeek = weekOffset < 0

  const isRecipeMode = plans.some((p) => p.meal_plan.some((m) => m.meal_type != null))
  const hasRecipeIds = plans.some((p) =>
    p.meal_plan.some((m) => m.meal_type === 'dinner' && m.recipe?.id)
  )
  const savedRecipeFilters = useMemo<RecipeFilters>(() => {
    const filters = plans[0]?.plan_meta?.recipe_filters
    if (!filters || !filters.allowed_sources?.length) return DEFAULT_RECIPE_FILTERS
    return {
      allowed_sources: filters.allowed_sources,
      prefer_favorites: filters.prefer_favorites ?? true,
      exclude_disliked: filters.exclude_disliked ?? true,
      prefer_variety: filters.prefer_variety ?? true,
    }
  }, [plans])

  useEffect(() => {
    if (!session?.access_token) return

    const token = session.access_token
    setLoading(true)
    setError('')
    setIsEmpty(false)

    Promise.all([
      getWeeklyPlans(token, startDate),
      getStapleFoods(token),
      getFavorites(token),
      getMyGoal(token),
    ])
      .then(([weeklyRes, staplesRes, favRes, goalRes]) => {
        if (weeklyRes.plans.length === 0) {
          if (weekOffset === 0) {
            router.push('/staple?from=plans')
            return
          }
          setIsEmpty(true)
          setPlans([])
        } else {
          setPlans(weeklyRes.plans)
        }
        setStaples(staplesRes)
        setFavoriteRecipeIds(new Set(favRes.map((f) => f.recipe_id)))
        setGoal(goalRes)
      })
      .catch((err) => {
        const info = err instanceof ApiError ? getErrorInfo(err.errorCode) : getErrorInfo()
        setError(info.message)
      })
      .finally(() => setLoading(false))
  }, [session?.access_token, router, startDate, weekOffset])

  const handlePatchMeal = async (planId: string, stapleName: string) => {
    if (!session?.access_token) return
    const updated = await patchMeal(session.access_token, planId, { staple_name: stapleName })
    setPlans((prev) => prev.map((p) => (p.id === planId ? updated : p)))
  }

  const handlePatchRecipe = useCallback(async (planId: string, recipeFilters: RecipeFilters) => {
    if (!session?.access_token) return
    try {
      const updated = await patchRecipe(session.access_token, planId, {
        recipe_filters: recipeFilters,
      })
      const weeklyRes = await getWeeklyPlans(session.access_token, startDate)
      setPlans(weeklyRes.plans.map((p) => (p.id === planId ? updated : p)))
    } catch (err) {
      const info = err instanceof ApiError ? getErrorInfo(err.errorCode) : getErrorInfo()
      if (err instanceof ApiError && err.status === 409) {
        const weeklyRes = await getWeeklyPlans(session.access_token, startDate)
        setPlans(weeklyRes.plans)
      }
      toast.error(info.message)
    }
  }, [session?.access_token, startDate])

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
      toast.error('お気に入りの更新に失敗しました')
    }
  }, [session?.access_token, favoriteRecipeIds])

  const fetchRecipeDetail = useCallback(async (recipeId: string): Promise<RecipeDetail> => {
    const cached = recipeCacheRef.current.get(recipeId)
    if (cached) return cached
    const token = session?.access_token
    if (!token) {
      throw new Error('認証情報が見つかりません')
    }
    const detail = await getRecipe(token, recipeId)
    recipeCacheRef.current.set(recipeId, detail)
    return detail
  }, [session?.access_token])

  const handleViewRecipe = useCallback((recipeId: string) => {
    setViewingRecipeId(recipeId)
  }, [])

  const handleShowShoppingList = async () => {
    setActiveTab('shopping')
    if (!session?.access_token) return
    setShoppingLoading(true)
    try {
      const [checks, data] = await Promise.all([
        getShoppingListChecks(session.access_token, startDate),
        getShoppingList(session.access_token, startDate),
      ])
      setCheckedGroupIds(new Set(checks.checked_group_ids))
      setShoppingList(data)
    } catch {
      setError('買い物リストの取得に失敗しました')
    } finally {
      setShoppingLoading(false)
    }
  }

  const handleToggleShoppingCheck = useCallback(async (groupId: string, checked: boolean) => {
    if (!session?.access_token) return

    setUpdatingGroupIds((prev) => new Set(prev).add(groupId))
    setCheckedGroupIds((prev) => {
      const next = new Set(prev)
      if (checked) {
        next.add(groupId)
      } else {
        next.delete(groupId)
      }
      return next
    })

    try {
      await setShoppingListCheck(session.access_token, {
        start_date: startDate,
        group_id: groupId,
        checked,
      })
      const data = await getShoppingList(session.access_token, startDate)
      setShoppingList(data)
    } catch {
      setCheckedGroupIds((prev) => {
        const rollback = new Set(prev)
        if (checked) {
          rollback.delete(groupId)
        } else {
          rollback.add(groupId)
        }
        return rollback
      })
      toast.error('買い物チェックの更新に失敗しました')
    } finally {
      setUpdatingGroupIds((prev) => {
        const next = new Set(prev)
        next.delete(groupId)
        return next
      })
    }
  }, [session?.access_token, startDate])

  const handleRegenerate = async (recipeFilters: RecipeFilters) => {
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
        start_date: startDate,
        mode: mode as 'classic' | 'recipe',
        staple_name: stapleName,
        recipe_filters: recipeFilters,
      })
      setPlans(result.plans)
      setShoppingList(null)
      toast.success('プランを再生成しました')
    } catch (err) {
      const info = err instanceof ApiError ? getErrorInfo(err.errorCode) : getErrorInfo()
      toast.error(info.message)
      setError(info.message)
    } finally {
      setRegenerating(false)
    }
  }

  const handleOpenRecipeSwapDialog = useCallback((planId: string) => {
    setPendingRecipePlanId(planId)
  }, [])

  const handleRecipeSwapConfirm = useCallback(async (recipeFilters: RecipeFilters) => {
    if (!pendingRecipePlanId) return
    setRegenerating(true)
    try {
      await handlePatchRecipe(pendingRecipePlanId, recipeFilters)
      setPendingRecipePlanId(null)
      toast.success('レシピを差し替えました')
    } finally {
      setRegenerating(false)
    }
  }, [handlePatchRecipe, pendingRecipePlanId])

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner />
        <p className="ml-2 text-muted-foreground">読み込み中...</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setWeekOffset((prev) => prev - 1)}
        >
          &larr; 前の週
        </Button>
        <span className="text-sm text-muted-foreground">
          {startDate} 〜
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setWeekOffset((prev) => prev + 1)}
          disabled={weekOffset >= 0}
        >
          次の週 &rarr;
        </Button>
      </div>

      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">
          週間メニュー{isPastWeek && ' (過去)'}
        </h1>
        {!isPastWeek && plans.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowRegenerateDialog(true)}
            disabled={regenerating}
          >
            {regenerating ? <><InlineSpinner /> 再生成中...</> : 'プランを再生成'}
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {isEmpty ? (
        <div className="flex flex-col items-center gap-4 rounded-md border p-8 text-center">
          <CalendarX2 className="h-12 w-12 text-muted-foreground" />
          <p className="text-muted-foreground">この週のプランはありません</p>
          {isPastWeek ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWeekOffset(0)}
            >
              今週に戻る
            </Button>
          ) : (
            <Link
              href="/staple?from=plans"
              className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90"
            >
              プランを作成する
            </Link>
          )}
        </div>
      ) : (
        <>
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
              goal={goal}
              onPatchMeal={isPastWeek ? undefined : handlePatchMeal}
              onChangeRecipe={isPastWeek ? undefined : handleOpenRecipeSwapDialog}
              onToggleFavorite={handleToggleFavorite}
              onViewRecipe={handleViewRecipe}
              favoriteRecipeIds={favoriteRecipeIds}
            />
          ) : (
            <ShoppingList
              data={shoppingList}
              loading={shoppingLoading}
              noRecipeIds={!hasRecipeIds}
              checkedGroupIds={checkedGroupIds}
              onToggleGroupChecked={handleToggleShoppingCheck}
              updatingGroupIds={updatingGroupIds}
            />
          )}
        </>
      )}

      <RecipeDetailModal
        open={viewingRecipeId !== null}
        recipeId={viewingRecipeId ?? undefined}
        isFavorite={viewingRecipeId ? favoriteRecipeIds.has(viewingRecipeId) : false}
        onClose={() => setViewingRecipeId(null)}
        onToggleFavorite={handleToggleFavorite}
        fetchRecipeDetail={fetchRecipeDetail}
      />

      <RecipeRegenerateDialog
        open={showRegenerateDialog}
        title="プランを再生成"
        description="現在のプランを上書きします。レシピソースや再生成条件を選んでください。"
        mode="weekly"
        initialFilters={savedRecipeFilters}
        submitting={regenerating}
        onConfirm={handleRegenerate}
        onCancel={() => setShowRegenerateDialog(false)}
      />

      <RecipeRegenerateDialog
        open={pendingRecipePlanId !== null}
        title="別のレシピに差し替え"
        description="現在のレシピを除外して、選択した条件の中から代替レシピを探します。"
        mode="single"
        initialFilters={savedRecipeFilters}
        submitting={regenerating}
        onConfirm={handleRecipeSwapConfirm}
        onCancel={() => setPendingRecipePlanId(null)}
      />
    </div>
  )
}
