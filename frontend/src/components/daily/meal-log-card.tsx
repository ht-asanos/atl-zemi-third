'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Star } from 'lucide-react'
import { MEAL_TYPE_LABELS } from '@/lib/constants'

interface MealLogCardProps {
  mealType: string
  completed: boolean
  satisfaction: number | null
  onCompletedChange: (completed: boolean) => void
  onSatisfactionChange: (satisfaction: number | null) => void
}

export function MealLogCard({
  mealType,
  completed,
  satisfaction,
  onCompletedChange,
  onSatisfactionChange,
}: MealLogCardProps) {
  return (
    <Card className="transition-shadow duration-200 hover:shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{MEAL_TYPE_LABELS[mealType] || mealType}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <Checkbox
            checked={completed}
            onCheckedChange={onCompletedChange}
            className="transition-transform duration-150 active:scale-90"
          />
          <span className={completed ? 'text-foreground font-medium' : 'text-muted-foreground'}>
            完了
          </span>
        </label>

        {completed && (
          <div className="animate-fade-in">
            <span className="text-sm text-muted-foreground">満足度</span>
            <div className="mt-1 flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => onSatisfactionChange(satisfaction === n ? null : n)}
                  aria-label={`満足度${n}`}
                  className="transition-transform duration-150 hover:scale-110 active:scale-95"
                >
                  <Star
                    className={`h-5 w-5 transition-colors duration-150 ${
                      satisfaction !== null && n <= satisfaction
                        ? 'fill-warning text-warning'
                        : 'text-muted'
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
