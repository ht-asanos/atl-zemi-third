'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const MEAL_TYPE_LABELS: Record<string, string> = {
  breakfast: '朝食',
  lunch: '昼食',
  dinner: '夕食',
}

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
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{MEAL_TYPE_LABELS[mealType] || mealType}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={completed}
            onChange={(e) => onCompletedChange(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          完了
        </label>

        {completed && (
          <div>
            <span className="text-sm text-muted-foreground">満足度</span>
            <div className="mt-1 flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => onSatisfactionChange(satisfaction === n ? null : n)}
                  className={`text-xl ${satisfaction !== null && n <= satisfaction ? 'text-yellow-400' : 'text-gray-300'}`}
                >
                  ★
                </button>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
