'use client'

import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import type { RecipeFilters } from '@/types/plan'

interface RecipeRegenerateDialogProps {
  open: boolean
  title: string
  description: string
  mode: 'weekly' | 'single'
  initialFilters: RecipeFilters
  submitting?: boolean
  onConfirm: (filters: RecipeFilters) => void
  onCancel: () => void
}

export function RecipeRegenerateDialog({
  open,
  title,
  description,
  mode,
  initialFilters,
  submitting = false,
  onConfirm,
  onCancel,
}: RecipeRegenerateDialogProps) {
  const [filters, setFilters] = useState<RecipeFilters>(initialFilters)

  useEffect(() => {
    if (open) {
      setFilters(initialFilters)
    }
  }, [open, initialFilters])

  const sourceError = useMemo(() => filters.allowed_sources.length === 0, [filters.allowed_sources])

  if (!open) return null

  const toggleSource = (source: 'rakuten' | 'youtube', checked: boolean) => {
    setFilters((prev) => {
      const nextSources = checked
        ? [...prev.allowed_sources, source]
        : prev.allowed_sources.filter((item) => item !== source)
      return {
        ...prev,
        allowed_sources: Array.from(new Set(nextSources)),
      }
    })
  }

  const toggleOption = (key: 'prefer_favorites' | 'exclude_disliked' | 'prefer_variety', checked: boolean) => {
    setFilters((prev) => ({ ...prev, [key]: checked }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <Card className="mx-4 w-full max-w-md">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <p className="text-sm text-muted-foreground">{description}</p>

          <div className="space-y-3">
            <div>
              <p className="text-sm font-medium">レシピソース</p>
              <p className="text-xs text-muted-foreground">少なくとも 1 つ選択してください</p>
            </div>
            <label className="flex items-center gap-3 text-sm">
              <Checkbox
                checked={filters.allowed_sources.includes('rakuten')}
                onCheckedChange={(checked) => toggleSource('rakuten', checked)}
              />
              楽天レシピ
            </label>
            <label className="flex items-center gap-3 text-sm">
              <Checkbox
                checked={filters.allowed_sources.includes('youtube')}
                onCheckedChange={(checked) => toggleSource('youtube', checked)}
              />
              YouTubeレシピ
            </label>
            {sourceError && <p className="text-xs text-destructive">少なくとも1つのソースを選択してください</p>}
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium">再生成オプション</p>
            <label className="flex items-center gap-3 text-sm">
              <Checkbox
                checked={filters.prefer_favorites}
                onCheckedChange={(checked) => toggleOption('prefer_favorites', checked)}
              />
              お気に入りを優先
            </label>
            <label className="flex items-center gap-3 text-sm">
              <Checkbox
                checked={filters.exclude_disliked}
                onCheckedChange={(checked) => toggleOption('exclude_disliked', checked)}
              />
              低評価レシピを除外
            </label>
            <label className="flex items-center gap-3 text-sm">
              <Checkbox
                checked={filters.prefer_variety}
                onCheckedChange={(checked) => toggleOption('prefer_variety', checked)}
              />
              できるだけ別ジャンルにする
            </label>
          </div>

          <div className="rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
            {mode === 'weekly'
              ? '今週ですでに使ったレシピは自動で避けます。'
              : '現在のレシピは自動で除外して候補を探します。'}
          </div>

          <div className="flex gap-2">
            <Button
              className="flex-1"
              onClick={() => onConfirm(filters)}
              disabled={submitting || sourceError}
            >
              {submitting ? '処理中...' : '実行する'}
            </Button>
            <Button variant="outline" className="flex-1" onClick={onCancel} disabled={submitting}>
              キャンセル
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
