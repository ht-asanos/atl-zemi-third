'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '@/providers/auth-provider'
import { getWeeklyPlans } from '@/lib/api/plans'
import { getMyGoal } from '@/lib/api/goals'
import {
  createMealLog,
  createWorkoutLog,
  getFeedbackHistory,
  getMealLogs,
  getWorkoutLogs,
  submitFeedback,
} from '@/lib/api/logs'
import { MealLogCard } from '@/components/daily/meal-log-card'
import { WorkoutLogCard } from '@/components/daily/workout-log-card'
import {
  FeedbackForm,
  type FeedbackTarget,
  type WorkoutFeedbackOption,
} from '@/components/daily/feedback-form'
import { AdaptationResult } from '@/components/daily/adaptation-result'
import { FeedbackHistory } from '@/components/daily/feedback-history'
import { DailyNutritionSummary } from '@/components/plans/daily-nutrition-summary'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Spinner, InlineSpinner } from '@/components/ui/spinner'
import { CalendarX2, Check } from 'lucide-react'
import { toast } from 'sonner'
import Link from 'next/link'
import type { DailyPlanResponse, Exercise } from '@/types/plan'
import type { AdaptationResponse, FeedbackEventDetailResponse } from '@/types/log'
import type { GoalResponse } from '@/types/goal'
import { ApiError } from '@/lib/api/client'
import { getErrorInfo } from '@/lib/errors'
import { buildTrainingSkillTreeHref } from '@/lib/training-skill-tree'
import { cn } from '@/lib/utils'
import { getTodayLocal, getMondayOfDateLocal } from '@/lib/date-utils'

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

export default function DailyContent() {
  const { session } = useAuth()
  const [todayPlan, setTodayPlan] = useState<DailyPlanResponse | null>(null)
  const [hasWeeklyPlan, setHasWeeklyPlan] = useState(false)
  const [goal, setGoal] = useState<GoalResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [error, setError] = useState('')
  const [adaptationResult, setAdaptationResult] = useState<AdaptationResponse | null>(null)
  const [feedbackHistory, setFeedbackHistory] = useState<FeedbackEventDetailResponse[]>([])
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const today = getTodayLocal()

  const [mealLogs, setMealLogs] = useState<Record<string, MealLogState>>(() =>
    Object.fromEntries(MEAL_TYPES.map((t) => [t, { completed: false, satisfaction: null }]))
  )
  const [workoutLogs, setWorkoutLogs] = useState<Record<string, WorkoutLogState>>({})

  useEffect(() => {
    return () => {
      if (savedTimerRef.current) clearTimeout(savedTimerRef.current)
    }
  }, [])

  const loadFeedbackHistory = useCallback(async (token: string) => {
    setHistoryLoading(true)
    try {
      const history = await getFeedbackHistory(token, 10)
      setFeedbackHistory(history)
    } catch {
      setFeedbackHistory([])
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const loadData = useCallback(async () => {
    if (!session?.access_token) return
    const token = session.access_token

    try {
      setHistoryLoading(true)
      const monday = getMondayOfDateLocal(today)
      const [weeklyRes, mealRes, workoutRes, goalRes, historyRes] = await Promise.all([
        getWeeklyPlans(token, monday),
        getMealLogs(token, today),
        getWorkoutLogs(token, today),
        getMyGoal(token),
        getFeedbackHistory(token, 10).catch(() => []),
      ])
      setGoal(goalRes)
      setFeedbackHistory(historyRes)

      setHasWeeklyPlan(weeklyRes.plans.length > 0)
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
      setHistoryLoading(false)
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
    setSaved(false)
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
      toast.success('記録を保存しました')
      setSaved(true)
      if (savedTimerRef.current) clearTimeout(savedTimerRef.current)
      savedTimerRef.current = setTimeout(() => setSaved(false), 2000)
    } catch {
      toast.error('記録の保存に失敗しました')
      setError('記録の保存に失敗しました')
    } finally {
      setSaving(false)
    }
  }

  const handleFeedback = async (text: string, target: FeedbackTarget, exerciseId?: string) => {
    if (!session?.access_token || !todayPlan) return
    setFeedbackLoading(true)
    setError('')

    try {
      const dinnerFeedbackPayload = target === 'meal' && dinnerRecipe
        ? {
            domain: 'meal' as const,
            meal_type: 'dinner' as const,
            satisfaction: mealLogs.dinner.satisfaction,
            completed: mealLogs.dinner.completed,
          }
        : {}
      const workoutFeedbackPayload = target === 'workout' && exerciseId
        ? {
            domain: 'workout' as const,
            exercise_id: exerciseId,
            rpe: workoutLogs[exerciseId]?.rpe ?? null,
            completed: workoutLogs[exerciseId]?.completed ?? false,
          }
        : {}
      const result = await submitFeedback(session.access_token, {
        plan_id: todayPlan.id,
        source_text: text,
        ...dinnerFeedbackPayload,
        ...workoutFeedbackPayload,
      })
      setAdaptationResult(result)
      if (result.new_plan) {
        setTodayPlan(result.new_plan)
      }
      await loadFeedbackHistory(session.access_token)
      toast.success('フィードバックを送信しました')
    } catch (e) {
      const info = e instanceof ApiError ? getErrorInfo(e.errorCode) : getErrorInfo()
      if (e instanceof ApiError && e.status === 409) {
        setError('他の操作と競合しました。リロードしてください。')
        toast.error('他の操作と競合しました')
      } else {
        setError(info.message)
        toast.error(info.message)
      }
    } finally {
      setFeedbackLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner />
        <p className="ml-2 text-muted-foreground">読み込み中...</p>
      </div>
    )
  }

  if (!todayPlan) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-bold">Today - {today}</h1>
          <Link href="/plans" className="text-sm text-muted-foreground hover:text-foreground">
            &larr; 週間プランに戻る
          </Link>
        </div>
        <div className="flex flex-col items-center gap-4 rounded-md border p-8 text-center">
          <CalendarX2 className="h-12 w-12 text-muted-foreground" />
          {hasWeeklyPlan ? (
            <>
              <p className="text-muted-foreground">今日({today})はプランに含まれていません</p>
              <Link
                href="/plans"
                className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90"
              >
                週間プランを確認する
              </Link>
            </>
          ) : (
            <>
              <p className="text-muted-foreground">今週のプランがまだ作成されていません</p>
              <div className="flex gap-3">
                <Link
                  href="/staple"
                  className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90"
                >
                  プランを作成する
                </Link>
                <Link
                  href="/plans"
                  className="inline-flex h-10 items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  週間プランを確認する
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  const exercises: Exercise[] =
    todayPlan.workout_plan && 'exercises' in todayPlan.workout_plan
      ? (todayPlan.workout_plan as { exercises: Exercise[] }).exercises
      : []
  const skillTreeHref = buildTrainingSkillTreeHref(
    todayPlan.plan_date,
    todayPlan.plan_meta?.available_equipment
  )
  const workoutFeedbackOptions: WorkoutFeedbackOption[] = exercises.map((exercise) => ({
    exerciseId: exercise.id,
    label: exercise.name_ja,
  }))

  // 今日の夕食レシピ情報
  const dinnerMeal = todayPlan.meal_plan.find((m) => m.meal_type === 'dinner')
  const dinnerRecipe = dinnerMeal?.recipe

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Today - {today}</h1>
        <Link href="/plans" className="text-sm text-muted-foreground hover:text-foreground">
          &larr; 週間プランに戻る
        </Link>
      </div>

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

      {/* Today's Dinner Recipe Summary */}
      {dinnerRecipe && (
        <section className="mb-6 rounded-md border p-4">
          <h2 className="mb-2 text-lg font-semibold">今日の夕食レシピ</h2>
          <div className="flex items-center gap-4">
            {dinnerRecipe.image_url && (
              <img
                src={dinnerRecipe.image_url}
                alt={dinnerRecipe.title}
                className="h-16 w-16 rounded-md object-cover"
              />
            )}
            <div>
              <p className="font-medium">{dinnerRecipe.title}</p>
              {dinnerRecipe.nutrition_per_serving?.kcal != null && (
                <p className="text-sm text-muted-foreground">{dinnerRecipe.nutrition_per_serving.kcal} kcal</p>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Daily Nutrition Summary */}
      {todayPlan.meal_plan.length > 0 && (
        <div className="mb-6">
          <DailyNutritionSummary meals={todayPlan.meal_plan} goal={goal} />
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
          <div className="mb-3 flex items-end justify-between gap-3">
            <h2 className="text-xl font-semibold">
              トレーニング
              {todayPlan.workout_plan && 'day_label' in todayPlan.workout_plan && (
                <span className="ml-2 text-base font-normal text-muted-foreground">
                  ({(todayPlan.workout_plan as { day_label: string }).day_label})
                </span>
              )}
            </h2>
            <Link href={skillTreeHref} className="text-sm text-primary underline">
              スキルツリーを見る
            </Link>
          </div>
          {todayPlan.plan_meta?.training_recommendations?.length ? (
            <div className="mb-3 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
              <p className="mb-2 font-medium">今回のトレーニング調整</p>
              <ul className="space-y-1">
                {todayPlan.plan_meta.training_recommendations.map((rec) => (
                  <li key={`${rec.from_exercise_id}-${rec.to_exercise_id}`}>{rec.reason}</li>
                ))}
              </ul>
            </div>
          ) : null}
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
      <Button
        onClick={handleSave}
        disabled={saving}
        className={cn('mb-6 w-full', saved && 'bg-green-600 hover:bg-green-600')}
      >
        {saving ? (
          <><InlineSpinner /> 保存中...</>
        ) : saved ? (
          <><Check className="mr-2 h-4 w-4" /> 保存しました</>
        ) : (
          '記録する'
        )}
      </Button>

      <Separator className="my-6" />

      {/* Feedback Section */}
      <section className="space-y-4">
        <FeedbackForm
          onSubmit={handleFeedback}
          isLoading={feedbackLoading}
          enableMealFeedback={Boolean(dinnerRecipe)}
          workoutOptions={workoutFeedbackOptions}
        />
        <FeedbackHistory items={feedbackHistory} isLoading={historyLoading} />
      </section>
    </div>
  )
}
