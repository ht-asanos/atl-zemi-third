'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AdaptationResponse } from '@/types/log'

const TAG_LABELS: Record<string, string> = {
  too_hard: 'きつすぎる',
  cannot_complete_reps: 'レップこなせない',
  forearm_sore: '前腕が痛い',
  bored_staple: '主食に飽きた',
  too_much_food: '食事量多い',
}

interface AdaptationResultProps {
  result: AdaptationResponse
  onClose: () => void
}

export function AdaptationResult({ result, onClose }: AdaptationResultProps) {
  return (
    <Card className="border-2 border-primary/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">適応結果</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {result.extraction_status === 'failed' && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            タグ抽出に失敗しました。感想は保存済みです。
          </div>
        )}

        {result.tags_applied.length > 0 && (
          <div>
            <span className="text-sm font-medium">抽出タグ</span>
            <div className="mt-1 flex flex-wrap gap-1">
              {result.tags_applied.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {TAG_LABELS[tag] || tag}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {result.changes_summary.length > 0 && (
          <div>
            <span className="text-sm font-medium">変更内容</span>
            <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
              {result.changes_summary.map((change, i) => (
                <li key={i}>- {change}</li>
              ))}
            </ul>
          </div>
        )}

        {result.tags_applied.length === 0 && result.extraction_status !== 'failed' && (
          <p className="text-sm text-muted-foreground">
            該当するタグはありませんでした。プランの変更はありません。
          </p>
        )}

        <Button onClick={onClose} variant="outline" size="sm" className="w-full">
          OK
        </Button>
      </CardContent>
    </Card>
  )
}
