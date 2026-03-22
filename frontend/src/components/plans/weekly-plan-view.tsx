'use client'

import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { DAY_SHORT } from '@/lib/constants'
import { DailyPlanCard } from './daily-plan-card'
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

export function WeeklyPlanView({ plans, staples, goal, onPatchMeal, onChangeRecipe, onToggleFavorite, onViewRecipe, favoriteRecipeIds }: WeeklyPlanViewProps) {
  const [changingPlanId, setChangingPlanId] = useState<string | null>(null)
  const [selectedStaple, setSelectedStaple] = useState('')
  const [patching, setPatching] = useState(false)

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
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setChangingPlanId(null)}
                >
                  キャンセル
                </Button>
                <Button
                  className="flex-1"
                  onClick={handleConfirmChange}
                  disabled={patching}
                >
                  {patching ? '変更中...' : '変更'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="0">
        <TabsList className="w-full flex-wrap">
          {plans.map((plan, i) => (
            <TabsTrigger key={plan.id} value={String(i)}>
              {DAY_SHORT[i] ?? `Day${i + 1}`}
            </TabsTrigger>
          ))}
        </TabsList>

        {plans.map((plan, i) => (
          <TabsContent key={plan.id} value={String(i)}>
            <DailyPlanCard
              plan={plan}
              goal={goal}
              onChangeMeal={onPatchMeal ? handleChangeMeal : undefined}
              onChangeRecipe={onChangeRecipe}
              onToggleFavorite={onToggleFavorite}
              onViewRecipe={onViewRecipe}
              favoriteRecipeIds={favoriteRecipeIds}
            />
          </TabsContent>
        ))}
      </Tabs>
    </>
  )
}
