'use client'

interface DailyProgressBarProps {
  completedMeals: number
  totalMeals: number
  completedWorkouts: number
  totalWorkouts: number
}

export function DailyProgressBar({
  completedMeals,
  totalMeals,
  completedWorkouts,
  totalWorkouts,
}: DailyProgressBarProps) {
  const total = totalMeals + totalWorkouts
  const completed = completedMeals + completedWorkouts

  if (total === 0) return null

  const segments = [
    ...Array.from({ length: totalMeals }, (_, i) => ({ type: 'meal' as const, done: i < completedMeals })),
    ...Array.from({ length: totalWorkouts }, (_, i) => ({ type: 'workout' as const, done: i < completedWorkouts })),
  ]

  return (
    <div className="mb-6 rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">今日の達成度</span>
        <span className="text-sm text-muted-foreground">
          {completed}/{total} 完了
        </span>
      </div>
      <div className="flex gap-1">
        {segments.map((seg, i) => (
          <div
            key={i}
            className="h-2 flex-1 rounded-full transition-colors duration-300"
            style={{
              backgroundColor: seg.done
                ? seg.type === 'meal'
                  ? 'var(--success)'
                  : 'var(--info)'
                : 'var(--muted)',
            }}
          />
        ))}
      </div>
      {completed === total && total > 0 && (
        <p className="mt-2 text-xs font-medium text-success animate-celebrate">
          🎉 今日のタスクをすべて完了しました！
        </p>
      )}
    </div>
  )
}
