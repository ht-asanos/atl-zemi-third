'use client'

import type { MealSuggestion } from '@/types/plan'
import type { GoalResponse } from '@/types/goal'

interface DailyNutritionSummaryProps {
  meals: MealSuggestion[]
  goal?: GoalResponse | null
}

interface NutritionBar {
  label: string
  unit: string
  actual: number
  target?: number
}

function progressColor(pct: number): string {
  if (pct >= 80 && pct <= 120) return 'bg-green-500'
  if ((pct >= 60 && pct < 80) || (pct > 120 && pct <= 140)) return 'bg-amber-400'
  return 'bg-red-400'
}

export function DailyNutritionSummary({ meals, goal }: DailyNutritionSummaryProps) {
  const totalKcal = meals.reduce((s, m) => s + (m.total_kcal ?? 0), 0)
  const totalProtein = meals.reduce((s, m) => s + (m.total_protein_g ?? 0), 0)
  const totalFat = meals.reduce((s, m) => s + (m.total_fat_g ?? 0), 0)
  const totalCarbs = meals.reduce((s, m) => s + (m.total_carbs_g ?? 0), 0)

  const bars: NutritionBar[] = [
    { label: 'kcal', unit: 'kcal', actual: totalKcal, target: goal?.target_kcal },
    { label: 'P', unit: 'g', actual: totalProtein, target: goal?.protein_g },
    { label: 'F', unit: 'g', actual: totalFat, target: goal?.fat_g },
    { label: 'C', unit: 'g', actual: totalCarbs, target: goal?.carbs_g },
  ]

  return (
    <div className="rounded-md border p-3">
      <p className="mb-2 text-sm font-semibold text-muted-foreground">1日の栄養</p>
      <div className="space-y-2">
        {bars.map(({ label, unit, actual, target }) => {
          const pct = target ? Math.round((actual / target) * 100) : null
          return (
            <div key={label} className="flex items-center gap-2 text-sm">
              <span className="w-6 shrink-0 font-medium">{label}</span>
              {target ? (
                <>
                  <div className="flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-2 rounded-full transition-all ${progressColor(pct!)}`}
                      style={{ width: `${Math.min(pct!, 100)}%` }}
                    />
                  </div>
                  <span className="w-40 shrink-0 text-right text-muted-foreground">
                    {Math.round(actual)}{unit} / {target}{unit}{' '}
                    <span className="text-xs">({pct}%)</span>
                  </span>
                </>
              ) : (
                <span className="text-muted-foreground">
                  {Math.round(actual)}{unit}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
