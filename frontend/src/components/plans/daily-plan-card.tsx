'use client'

import { Separator } from '@/components/ui/separator'
import { DAY_NAMES } from '@/lib/constants'
import { MealSection } from './meal-section'
import { WorkoutSection } from './workout-section'
import type { DailyPlanResponse } from '@/types/plan'

interface DailyPlanCardProps {
  plan: DailyPlanResponse
  onChangeMeal?: (planId: string) => void
  onChangeRecipe?: (planId: string) => void
  onToggleFavorite?: (recipeId: string) => void
  favoriteRecipeIds?: Set<string>
}

export function DailyPlanCard({ plan, onChangeMeal, onChangeRecipe, onToggleFavorite, favoriteRecipeIds }: DailyPlanCardProps) {
  const d = new Date(plan.plan_date + 'T00:00:00')
  const dayLabel = `${d.getMonth() + 1}/${d.getDate()} (${DAY_NAMES[d.getDay()]})`

  // recipe モード判定: meal_plan 内に meal_type があれば recipe モード
  const isRecipeMode = plan.meal_plan.some((m) => m.meal_type != null)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold">{dayLabel}</h3>
        {!isRecipeMode && onChangeMeal && (
          <button
            onClick={() => onChangeMeal(plan.id)}
            className="text-sm text-primary underline"
          >
            主食を変更
          </button>
        )}
      </div>

      <div className="space-y-3">
        <h4 className="text-lg font-semibold">食事</h4>
        {plan.meal_plan.map((meal, i) => (
          <MealSection
            key={i}
            meals={plan.meal_plan}
            mealIndex={i}
            onChangeRecipe={
              isRecipeMode && meal.meal_type === 'dinner' && meal.recipe && onChangeRecipe
                ? () => onChangeRecipe(plan.id)
                : undefined
            }
            onToggleFavorite={onToggleFavorite}
            favoriteRecipeIds={favoriteRecipeIds}
          />
        ))}
      </div>

      <Separator />

      <div>
        <h4 className="mb-2 text-lg font-semibold">トレーニング</h4>
        <WorkoutSection workout={plan.workout_plan} />
      </div>
    </div>
  )
}
