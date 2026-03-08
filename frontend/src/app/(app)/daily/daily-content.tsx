'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '@/providers/auth-provider'
import { getWeeklyPlans } from '@/lib/api/plans'
import {
  createMealLog,
  createWorkoutLog,
  getMealLogs,
  getWorkoutLogs,
  submitFeedback,
} from '@/lib/api/logs'
import { MealLogCard } from '@/components/daily/meal-log-card'
import { WorkoutLogCard } from '@/components/daily/workout-log-card'
import { FeedbackForm } from '@/components/daily/feedback-form'
import { AdaptationResult } from '@/components/daily/adaptation-result'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import type { DailyPlanResponse, Exercise } from '@/types/plan'
import type { AdaptationResponse } from '@/types/log'
import { ApiError } from '@/lib/api/client'

const MEAL_TYPES = ['breakfast', 'lunch', 'dinner'] as const

interface MealLogState {
  completed: boolean
  satisfaction: number | null
}

interface WorkoutLogState {
  completed: boolean
  sets: number
  reps: number
  rpe: number | null
}

function getTodayString(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function getMondayOfDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  return d.toISOString().slice(0, 10)
}

export default function DailyContent() {
  const { session } = useAuth()
  const [todayPlan, setTodayPlan] = useState<DailyPlanResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  const [error, setError] = useState('')
  const [adaptationResult, setAdaptationResult] = useState<AdaptationResponse | null>(null)

  const today = getTodayString()

  const [mealLogs, setMealLogs] = useState<Record<string, MealLogState>>(() =>
    Object.fromEntries(MEAL_TYPES.map((t) => [t, { completed: false, satisfaction: null }]))
  )
  const [workoutLogs, setWorkoutLogs] = useState<Record<string, WorkoutLogState>>({})

  const loadData = useCallback(async () => {
    if (!session?.access_token) return
    const token = session.access_token

    try {
      const monday = getMondayOfDate(today)
      const [weeklyRes, mealRes, workoutRes] = await Promise.all([
        getWeeklyPlans(token, monday),
        getMealLogs(token, today),
        getWorkoutLogs(token, today),
      ])

      const plan = weeklyRes.plans.find((p) => p.plan_date === today) ?? null
      setTodayPlan(plan)

      // Restore meal logs
      const restoredMeals: Record<string, MealLogState> = Object.fromEntries(
        MEAL_TYPES.map((t) => [t, { completed: false, satisfaction: null }])
      )
      for (const log of mealRes.logs) {
        restoredMeals[log.meal_type] = {
          completed: log.completed,
          satisfaction: log.satisfaction,
        }
      }
      setMealLogs(restoredMeals)

      // Restore workout logs
      if (plan && plan.workout_plan && 'exercises' in plan.workout_plan) {
        const restoredWorkouts: Record<string, WorkoutLogState> = {}
        const exercises = (plan.workout_plan as { exercises: Exercise[] }).exercises
        for (const ex of exercises) {
          const existing = workoutRes.logs.find((l) => l.exercise_id === ex.id)
          restoredWorkouts[ex.id] = existing
            ? { completed: existing.completed, sets: existing.sets, reps: existing.reps, rpe: existing.rpe }
            : { completed: false, sets: typeof ex.sets === 'number' ? ex.sets : 0, reps: typeof ex.reps === 'number' ? ex.reps : 0, rpe: null }
        }
        setWorkoutLogs(restoredWorkouts)
      }
    } catch {
      setError('データの取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }, [session?.access_token, today])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleSave = async () => {
    if (!session?.access_token || !todayPlan) return
    const token = session.access_token
    setSaving(true)
    setError('')

    try {
      // Save meal logs
      const mealPromises = MEAL_TYPES.map((mealType) =>
        createMealLog(token, {
          plan_id: todayPlan.id,
          log_date: today,
          meal_type: mealType,
          completed: mealLogs[mealType].completed,
          satisfaction: mealLogs[mealType].satisfaction,
        })
      )

      // Save workout logs
      const workoutPromises = Object.entries(workoutLogs).map(([exerciseId, state]) =>
        createWorkoutLog(token, {
          plan_id: todayPlan.id,
          log_date: today,
          exercise_id: exerciseId,
          sets: state.sets,
          reps: state.reps,
          rpe: state.rpe,
          completed: state.completed,
        })
      )

      await Promise.all([...mealPromises, ...workoutPromises])
    } catch {
      setError('記録の保存に失敗しました')
    } finally {
      setSaving(false)
    }
  }

  const handleFeedback = async (text: string) => {
    if (!session?.access_token || !todayPlan) return
    setFeedbackLoading(true)
    setError('')

    try {
      const result = await submitFeedback(session.access_token, {
        plan_id: todayPlan.id,
        source_text: text,
      })
      setAdaptationResult(result)
      if (result.new_plan) {
        setTodayPlan(result.new_plan)
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError('他の操作と競合しました。リロードしてください。')
      } else {
        setError('フィードバックの送信に失敗しました')
      }
    } finally {
      setFeedbackLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">読み込み中...</p>
      </div>
    )
  }

  if (!todayPlan) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <h1 className="mb-4 text-3xl font-bold">Today</h1>
        <p className="text-muted-foreground">今日のプランがありません。先に週間プランを作成してください。</p>
      </div>
    )
  }

  const exercises: Exercise[] =
    todayPlan.workout_plan && 'exercises' in todayPlan.workout_plan
      ? (todayPlan.workout_plan as { exercises: Exercise[] }).exercises
      : []

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="mb-6 text-3xl font-bold">Today - {today}</h1>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {adaptationResult && (
        <div className="mb-4">
          <AdaptationResult result={adaptationResult} onClose={() => setAdaptationResult(null)} />
        </div>
      )}

      {/* Meal Section */}
      <section className="mb-6">
        <h2 className="mb-3 text-xl font-semibold">食事</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {MEAL_TYPES.map((mealType) => (
            <MealLogCard
              key={mealType}
              mealType={mealType}
              completed={mealLogs[mealType].completed}
              satisfaction={mealLogs[mealType].satisfaction}
              onCompletedChange={(completed) =>
                setMealLogs((prev) => ({ ...prev, [mealType]: { ...prev[mealType], completed } }))
              }
              onSatisfactionChange={(satisfaction) =>
                setMealLogs((prev) => ({ ...prev, [mealType]: { ...prev[mealType], satisfaction } }))
              }
            />
          ))}
        </div>
      </section>

      <Separator className="my-6" />

      {/* Workout Section */}
      {exercises.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-xl font-semibold">
            トレーニング
            {todayPlan.workout_plan && 'day_label' in todayPlan.workout_plan && (
              <span className="ml-2 text-base font-normal text-muted-foreground">
                ({(todayPlan.workout_plan as { day_label: string }).day_label})
              </span>
            )}
          </h2>
          <div className="space-y-3">
            {exercises.map((ex) => (
              <WorkoutLogCard
                key={ex.id}
                exerciseId={ex.id}
                nameJa={ex.name_ja}
                plannedSets={ex.sets}
                plannedReps={ex.reps}
                completed={workoutLogs[ex.id]?.completed ?? false}
                sets={workoutLogs[ex.id]?.sets ?? (typeof ex.sets === 'number' ? ex.sets : 0)}
                reps={workoutLogs[ex.id]?.reps ?? (typeof ex.reps === 'number' ? ex.reps : 0)}
                rpe={workoutLogs[ex.id]?.rpe ?? null}
                onCompletedChange={(completed) =>
                  setWorkoutLogs((prev) => ({
                    ...prev,
                    [ex.id]: { ...prev[ex.id], completed },
                  }))
                }
                onSetsChange={(sets) =>
                  setWorkoutLogs((prev) => ({
                    ...prev,
                    [ex.id]: { ...prev[ex.id], sets },
                  }))
                }
                onRepsChange={(reps) =>
                  setWorkoutLogs((prev) => ({
                    ...prev,
                    [ex.id]: { ...prev[ex.id], reps },
                  }))
                }
                onRpeChange={(rpe) =>
                  setWorkoutLogs((prev) => ({
                    ...prev,
                    [ex.id]: { ...prev[ex.id], rpe },
                  }))
                }
              />
            ))}
          </div>
        </section>
      )}

      <Separator className="my-6" />

      {/* Save Button */}
      <Button onClick={handleSave} disabled={saving} className="mb-6 w-full">
        {saving ? '保存中...' : '記録する'}
      </Button>

      <Separator className="my-6" />

      {/* Feedback Section */}
      <section>
        <FeedbackForm onSubmit={handleFeedback} isLoading={feedbackLoading} />
      </section>
    </div>
  )
}
