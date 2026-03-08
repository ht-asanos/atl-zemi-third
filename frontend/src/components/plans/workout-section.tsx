'use client'

import type { TrainingDay } from '@/types/plan'

interface WorkoutSectionProps {
  workout: TrainingDay | Record<string, never>
}

export function WorkoutSection({ workout }: WorkoutSectionProps) {
  if (!('day_label' in workout) || !workout.exercises?.length) {
    return (
      <div className="rounded-md border p-3">
        <p className="text-sm text-muted-foreground">休息日</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <h4 className="font-semibold">{workout.day_label}</h4>
      <div className="rounded-md border p-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2">種目</th>
              <th className="pb-2">セット</th>
              <th className="pb-2">レップ</th>
              <th className="pb-2">休憩</th>
            </tr>
          </thead>
          <tbody>
            {workout.exercises.map((ex) => (
              <tr key={ex.id} className="border-b last:border-0">
                <td className="py-2">{ex.name_ja}</td>
                <td className="py-2">{ex.sets}</td>
                <td className="py-2">{ex.reps}</td>
                <td className="py-2">{ex.rest_seconds}秒</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
