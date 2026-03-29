'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { FeedbackEventDetailResponse } from '@/types/log'

const TAG_LABELS: Record<string, string> = {
  too_hard: 'きつすぎる',
  cannot_complete_reps: 'レップこなせない',
  forearm_sore: '前腕が痛い',
  bored_staple: '主食に飽きた',
  too_much_food: '食事量多い',
}

const DOMAIN_LABELS: Record<FeedbackEventDetailResponse['domain'], string> = {
  meal: '食事',
  workout: 'トレーニング',
  mixed: '混合',
}

const MEAL_TYPE_LABELS: Record<NonNullable<FeedbackEventDetailResponse['meal_type']>, string> = {
  breakfast: '朝食',
  lunch: '昼食',
  dinner: '夕食',
  snack: '間食',
}

const TARGET_TYPE_LABELS: Record<string, string> = {
  meal_plan: '食事プラン',
  recipe_selection: 'レシピ選定',
  workout_plan: '運動プラン',
}

function getRecipeSelectionMessage(changeSummary: string[]): string {
  for (const change of changeSummary) {
    if (change.endsWith('→1')) {
      return '次回の夕食候補で優先します。'
    }
    if (change.endsWith('→-1')) {
      return '次回の夕食候補で優先度を下げます。'
    }
  }
  return '次回の夕食候補への反映を更新しました。'
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('ja-JP', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface FeedbackHistoryProps {
  items: FeedbackEventDetailResponse[]
  isLoading: boolean
}

export function FeedbackHistory({ items, isLoading }: FeedbackHistoryProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">フィードバック履歴</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          履歴を読み込み中...
        </CardContent>
      </Card>
    )
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">フィードバック履歴</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          まだ履歴はありません。送信した内容とプラン変更がここに残ります。
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">フィードバック履歴</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item) => (
          <div key={item.id} className="rounded-lg border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{DOMAIN_LABELS[item.domain]}</Badge>
              {item.meal_type && (
                <Badge variant="secondary">{MEAL_TYPE_LABELS[item.meal_type]}</Badge>
              )}
              {item.completed != null && (
                <Badge variant="secondary">{item.completed ? '完了' : '未完了'}</Badge>
              )}
              <span className="text-xs text-muted-foreground">
                {formatDateTime(item.created_at)}
              </span>
            </div>

            <p className="mt-2 text-sm leading-6">{item.source_text}</p>

            {(item.satisfaction != null || item.rpe != null || item.exercise_id) && (
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {item.satisfaction != null && <span>満足度 {item.satisfaction}/5</span>}
                {item.rpe != null && <span>RPE {item.rpe}/10</span>}
                {item.exercise_id && <span>種目ID: {item.exercise_id}</span>}
              </div>
            )}

            {item.tags.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1">
                {item.tags.map((tag) => (
                  <Badge key={tag.id} variant="secondary">
                    {TAG_LABELS[tag.tag] || tag.tag}
                  </Badge>
                ))}
              </div>
            )}

            {item.adaptation_events.length > 0 && (
              <div className="mt-3 space-y-2">
                {item.adaptation_events.map((event) => (
                  <div key={event.id} className="rounded-md bg-muted/40 p-2">
                    <div className="text-xs font-medium text-foreground">
                      {TARGET_TYPE_LABELS[event.target_type] || event.target_type}
                    </div>
                    {event.target_type === 'recipe_selection' ? (
                      <div className="mt-1 space-y-1 text-xs text-muted-foreground">
                        <p>{getRecipeSelectionMessage(event.change_summary_json)}</p>
                        {event.target_ref && (
                          <p className="break-all">対象レシピID: {event.target_ref}</p>
                        )}
                      </div>
                    ) : event.change_summary_json.length > 0 && (
                      <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
                        {event.change_summary_json.map((change, index) => (
                          <li key={`${event.id}-${index}`}>- {change}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
