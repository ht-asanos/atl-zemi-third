'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface WorkoutLogCardProps {
  exerciseId: string
  nameJa: string
  plannedSets: number
  plannedReps: number | string
  completed: boolean
  sets: number
  reps: number
  rpe: number | null
  onCompletedChange: (completed: boolean) => void
  onSetsChange: (sets: number) => void
  onRepsChange: (reps: number) => void
  onRpeChange: (rpe: number | null) => void
}

export function WorkoutLogCard({
  nameJa,
  plannedSets,
  plannedReps,
  completed,
  sets,
  reps,
  rpe,
  onCompletedChange,
  onSetsChange,
  onRepsChange,
  onRpeChange,
}: WorkoutLogCardProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">
          {nameJa}
          <span className="ml-2 text-sm font-normal text-muted-foreground">
            (目標: {plannedSets}x{plannedReps})
          </span>
        </CardTitle>
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
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-xs">セット数</Label>
              <Input
                type="number"
                min={0}
                value={sets}
                onChange={(e) => onSetsChange(Number(e.target.value))}
                className="h-8"
              />
            </div>
            <div>
              <Label className="text-xs">レップ数</Label>
              <Input
                type="number"
                min={0}
                value={reps}
                onChange={(e) => onRepsChange(Number(e.target.value))}
                className="h-8"
              />
            </div>
            <div>
              <Label className="text-xs">RPE (1-10)</Label>
              <Input
                type="number"
                min={1}
                max={10}
                step={0.5}
                value={rpe ?? ''}
                onChange={(e) => {
                  const v = e.target.value
                  onRpeChange(v === '' ? null : Number(v))
                }}
                className="h-8"
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
