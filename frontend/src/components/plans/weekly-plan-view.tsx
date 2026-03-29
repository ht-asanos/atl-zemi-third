'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ChevronDown, Dumbbell, UtensilsCrossed } from 'lucide-react'
import { DAY_NAMES } from '@/lib/constants'
import { getTodayLocal } from '@/lib/date-utils'
import { DailyPlanCard } from './daily-plan-card'
import { cn } from '@/lib/utils'
import type { DailyPlanResponse } from '@/types/plan'
import type { FoodItem } from '@/types/food'
import type { GoalResponse } from '@/types/goal'

interface WeeklyPlanViewProps {
  plans: DailyPlanResponse[]
  staples: FoodItem[]
  goal?: GoalResponse | null
  onPatchMeal?: (planId: string, stapleName: string) => Promise<void>
  onChangeRecipe?: (planId: string) => void
  onToggleFavorite?: (recipeId: string) => void
  onViewRecipe?: (recipeId: string) => void
  favoriteRecipeIds?: Set<string>
}

function getDayLabel(planDate: string) {
  const d = new Date(planDate + 'T00:00:00')
  return `${d.getMonth() + 1}/${d.getDate()} (${DAY_NAMES[d.getDay()]})`
}

function getDinnerSummary(plan: DailyPlanResponse): string {
  const dinner = plan.meal_plan.find((m) => m.meal_type === 'dinner')
  if (dinner?.recipe?.title) return dinner.recipe.title
  if (dinner?.staple?.name) return dinner.staple.name
  const first = plan.meal_plan[0]
  return first?.staple?.name ?? '—'
}

function getWorkoutSummary(plan: DailyPlanResponse): string | null {
  const wp = plan.workout_plan
  if (!wp || !('day_label' in wp)) return null
  const exCount = (wp as { exercises?: unknown[] }).exercises?.length ?? 0
  return `${(wp as { day_label: string }).day_label} · ${exCount}種目`
}

export function WeeklyPlanView({
  plans,
  staples,
  goal,
  onPatchMeal,
  onChangeRecipe,
  onToggleFavorite,
  onViewRecipe,
  favoriteRecipeIds,
}: WeeklyPlanViewProps) {
  const today = getTodayLocal()
  const [changingPlanId, setChangingPlanId] = useState<string | null>(null)
  const [selectedStaple, setSelectedStaple] = useState('')
  const [patching, setPatching] = useState(false)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    const todayPlan = plans.find((p) => p.plan_date === today)
    return new Set(todayPlan ? [todayPlan.id] : plans.length ? [plans[0].id] : [])
  })

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleChangeMeal = (planId: string) => {
    setChangingPlanId(planId)
    setSelectedStaple(staples[0]?.name ?? '')
  }

  const handleConfirmChange = async () => {
    if (!changingPlanId || !selectedStaple) return
    setPatching(true)
    try {
      await onPatchMeal?.(changingPlanId, selectedStaple)
      setChangingPlanId(null)
    } finally {
      setPatching(false)
    }
  }

  if (plans.length === 0) return null

  return (
    <>
      {changingPlanId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-sm">
            <CardHeader>
              <CardTitle>主食を変更</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select
                value={selectedStaple}
                onChange={(e) => setSelectedStaple(e.target.value)}
              >
                {staples.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </Select>
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setChangingPlanId(null)}>
                  キャンセル
                </Button>
                <Button className="flex-1" onClick={handleConfirmChange} disabled={patching}>
                  {patching ? '変更中...' : '変更'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="space-y-3">
        {plans.map((plan) => {
          const isToday = plan.plan_date === today
          const isExpanded = expandedIds.has(plan.id)
          const dinner = getDinnerSummary(plan)
          const workout = getWorkoutSummary(plan)

          return (
            <div
              key={plan.id}
              className={cn(
                'rounded-xl border border-border bg-card overflow-hidden transition-all duration-200',
                isToday && 'ring-2 ring-primary border-primary'
              )}
            >
              {/* カードヘッダー（常時表示） */}
              <button
                type="button"
                onClick={() => toggleExpand(plan.id)}
                className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-muted/40 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={cn('text-sm font-semibold', isToday ? 'text-primary' : 'text-foreground')}>
                      {getDayLabel(plan.plan_date)}
                    </span>
                    {isToday && (
                      <Badge className="bg-primary text-primary-foreground text-xs px-1.5 py-0">今日</Badge>
                    )}
                  </div>
                  {!isExpanded && (
                    <div className="flex items-center gap-3 min-w-0 text-xs text-muted-foreground">
                      {dinner && (
                        <span className="flex items-center gap-1 truncate max-w-[140px]">
                          <UtensilsCrossed size={11} />
                          <span className="truncate">{dinner}</span>
                        </span>
                      )}
                      {workout && (
                        <span className="flex items-center gap-1 shrink-0">
                          <Dumbbell size={11} />
                          {workout}
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <ChevronDown
                  size={16}
                  className={cn(
                    'shrink-0 text-muted-foreground transition-transform duration-200',
                    isExpanded && 'rotate-180'
                  )}
                />
              </button>

              {/* 展開コンテンツ */}
              {isExpanded && (
                <div className="border-t border-border px-4 pb-4 pt-4 animate-fade-in">
                  <DailyPlanCard
                    plan={plan}
                    goal={goal}
                    onChangeMeal={onPatchMeal ? handleChangeMeal : undefined}
                    onChangeRecipe={onChangeRecipe}
                    onToggleFavorite={onToggleFavorite}
                    onViewRecipe={onViewRecipe}
                    favoriteRecipeIds={favoriteRecipeIds}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
