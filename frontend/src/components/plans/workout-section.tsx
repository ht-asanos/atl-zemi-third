'use client'

import Link from 'next/link'
import type { TrainingDay, TrainingRecommendation } from '@/types/plan'

interface WorkoutSectionProps {
  workout: TrainingDay | Record<string, never>
  recommendations?: TrainingRecommendation[] | null
  skillTreeHref?: string | null
}

export function WorkoutSection({ workout, recommendations, skillTreeHref }: WorkoutSectionProps) {
  if (!('day_label' in workout) || !workout.exercises?.length) {
    return (
      <div className="rounded-md border p-3">
        <p className="text-sm text-muted-foreground">休息日</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h4 className="font-semibold">{workout.day_label}</h4>
        {skillTreeHref ? (
          <Link href={skillTreeHref} className="text-sm text-primary underline">
            スキルツリーを見る
          </Link>
        ) : null}
      </div>
      {recommendations && recommendations.length > 0 && (
        <div className="rounded-md border border-info/30 bg-info/5 p-3 text-sm text-info">
          <p className="mb-2 font-medium">今回のトレーニング調整</p>
          <ul className="space-y-1">
            {recommendations.map((rec) => (
              <li key={`${rec.from_exercise_id}-${rec.to_exercise_id}`}>{rec.reason}</li>
            ))}
          </ul>
        </div>
      )}
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
