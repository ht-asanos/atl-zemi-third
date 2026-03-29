'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { InlineSpinner } from '@/components/ui/spinner'

export type FeedbackTarget = 'general' | 'meal' | 'workout'

export interface WorkoutFeedbackOption {
  exerciseId: string
  label: string
}

interface FeedbackFormProps {
  onSubmit: (text: string, target: FeedbackTarget, exerciseId?: string) => void
  isLoading: boolean
  enableMealFeedback?: boolean
  workoutOptions?: WorkoutFeedbackOption[]
}

export function FeedbackForm({
  onSubmit,
  isLoading,
  enableMealFeedback = false,
  workoutOptions = [],
}: FeedbackFormProps) {
  const [text, setText] = useState('')
  const [target, setTarget] = useState<FeedbackTarget>('general')
  const [selectedExerciseId, setSelectedExerciseId] = useState('')
  const enableWorkoutFeedback = workoutOptions.length > 0

  useEffect(() => {
    if (target === 'meal' && !enableMealFeedback) {
      setTarget('general')
    }
    if (target === 'workout' && !enableWorkoutFeedback) {
      setTarget('general')
    }
  }, [enableMealFeedback, enableWorkoutFeedback, target])

  const handleSubmit = () => {
    if (text.trim()) {
      onSubmit(text.trim(), target, selectedExerciseId || undefined)
    }
  }

  return (
    <div className="space-y-2">
      <Label>感想・フィードバック</Label>
      {(enableMealFeedback || enableWorkoutFeedback) && (
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={target === 'general' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setTarget('general')}
          >
            全体
          </Button>
          <Button
            type="button"
            variant={target === 'meal' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setTarget('meal')}
          >
            食事
          </Button>
          {enableWorkoutFeedback && (
            <Button
              type="button"
              variant={target === 'workout' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setTarget('workout')}
            >
              トレーニング
            </Button>
          )}
        </div>
      )}
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="例: トレーニングがきつすぎた、主食に飽きた..."
        maxLength={1000}
        rows={3}
      />
      {enableMealFeedback && target === 'meal' && (
        <p className="text-xs text-muted-foreground">
          食事を選ぶと、この夕食レシピの好みとして次回の候補選定に反映します。
        </p>
      )}
      {enableWorkoutFeedback && target === 'workout' && (
        <div className="space-y-2">
          <div>
            <Label className="text-xs">対象種目</Label>
            <Select
              value={selectedExerciseId}
              onChange={(e) => setSelectedExerciseId(e.target.value)}
              className="mt-1 h-9"
            >
              <option value="">種目を選択してください</option>
              {workoutOptions.map((option) => (
                <option key={option.exerciseId} value={option.exerciseId}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
          <p className="text-xs text-muted-foreground">
            トレーニングを選ぶと、選択した種目の完了状況と RPE を添えて記録します。
          </p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{text.length}/1000</span>
        <Button
          onClick={handleSubmit}
          disabled={isLoading || !text.trim() || (target === 'workout' && !selectedExerciseId)}
          size="sm"
        >
          {isLoading ? <><InlineSpinner /> 送信中...</> : 'フィードバック送信'}
        </Button>
      </div>
    </div>
  )
}
