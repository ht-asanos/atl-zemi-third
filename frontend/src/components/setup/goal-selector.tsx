'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { GoalType } from '@/types/goal'

const GOALS: { value: GoalType; label: string; description: string }[] = [
  { value: 'diet', label: 'ダイエット', description: '体脂肪を減らして引き締まった体へ' },
  { value: 'strength', label: '筋力アップ', description: '筋肉量を増やしてパワーアップ' },
  { value: 'bouldering', label: 'ボルダリング', description: '指力・体幹を鍛えてグレードアップ' },
]

interface GoalSelectorProps {
  value: GoalType
  onChange: (value: GoalType) => void
}

export function GoalSelector({ value, onChange }: GoalSelectorProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {GOALS.map((goal) => (
        <Card
          key={goal.value}
          className={cn(
            'cursor-pointer transition-colors hover:border-primary',
            value === goal.value && 'border-primary bg-primary/5'
          )}
          onClick={() => onChange(goal.value)}
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">{goal.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{goal.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
