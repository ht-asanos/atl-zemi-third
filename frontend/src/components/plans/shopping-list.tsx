'use client'

import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Spinner } from '@/components/ui/spinner'
import { RefreshCw, ShoppingCart } from 'lucide-react'
import type { ShoppingListResponse } from '@/types/plan'

interface ShoppingListProps {
  data: ShoppingListResponse | null
  loading: boolean
  noRecipeIds: boolean
  checkedGroupIds: Set<string>
  onToggleGroupChecked: (groupId: string, checked: boolean) => void
  updatingGroupIds: Set<string>
}

export function ShoppingList({
  data,
  loading,
  noRecipeIds,
  checkedGroupIds,
  onToggleGroupChecked,
  updatingGroupIds,
}: ShoppingListProps) {
  if (noRecipeIds) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-md border p-6 text-center text-sm text-muted-foreground">
        <RefreshCw className="h-8 w-8" />
        プランを再生成すると買い物リストが利用できます
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-6">
        <Spinner />
        <p className="ml-2 text-sm text-muted-foreground">読み込み中...</p>
      </div>
    )
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-md border p-6 text-center text-sm text-muted-foreground">
        <ShoppingCart className="h-8 w-8" />
        買い物リストが空です
      </div>
    )
  }

  // カテゴリ別にグループ化
  const groupedUnchecked: Record<string, typeof data.items> = {}
  const groupedChecked: Record<string, typeof data.items> = {}
  for (const item of data.items) {
    const cat = item.category_name || 'その他'
    const target = item.checked ? groupedChecked : groupedUnchecked
    if (!target[cat]) target[cat] = []
    target[cat].push(item)
  }

  const renderGroups = (grouped: Record<string, typeof data.items>, checkedStyle: boolean) =>
    Object.entries(grouped).map(([category, items]) => (
      <div key={`${checkedStyle ? 'checked' : 'unchecked'}-${category}`} className="space-y-2">
        <h4 className="text-sm font-semibold">{category}</h4>
        <div className="space-y-1">
          {items.map((item, i) => (
            <div
              key={i}
              className={`flex items-center justify-between rounded-md border px-3 py-2 ${checkedStyle ? 'bg-muted/40' : ''}`}
            >
              <div className="flex items-center gap-2">
                {item.group_id && (
                  <Checkbox
                    checked={checkedGroupIds.has(item.group_id)}
                    disabled={updatingGroupIds.has(item.group_id)}
                    onCheckedChange={(next) => onToggleGroupChecked(item.group_id!, next === true)}
                    aria-label={`${item.ingredient_name}をチェック`}
                  />
                )}
                <div>
                  <span className={`text-sm font-medium ${checkedStyle ? 'text-muted-foreground line-through' : ''}`}>
                    {item.ingredient_name}
                  </span>
                  {item.amount_g != null && item.amount_g > 0 && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {Math.round(item.amount_g)}g
                    </span>
                  )}
                  {item.amount_text && !item.amount_g && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {item.amount_text}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-1">
                {item.recipe_titles.map((title) => (
                  <Badge key={title} variant="outline" className="text-xs">
                    {title}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    ))

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {data.recipe_count} レシピ分の食材
      </p>
      <div className="space-y-3">
        <h3 className="text-sm font-semibold">未購入</h3>
        {Object.keys(groupedUnchecked).length > 0 ? (
          renderGroups(groupedUnchecked, false)
        ) : (
          <p className="text-sm text-muted-foreground">未購入の材料はありません</p>
        )}
      </div>
      <div className="space-y-3">
        <h3 className="text-sm font-semibold">購入済み</h3>
        {Object.keys(groupedChecked).length > 0 ? (
          renderGroups(groupedChecked, true)
        ) : (
          <p className="text-sm text-muted-foreground">まだチェックされていません</p>
        )}
      </div>
    </div>
  )
}
