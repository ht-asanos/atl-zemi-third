'use client'

import { Badge } from '@/components/ui/badge'
import type { ShoppingListResponse } from '@/types/plan'

interface ShoppingListProps {
  data: ShoppingListResponse | null
  loading: boolean
  noRecipeIds: boolean
}

export function ShoppingList({ data, loading, noRecipeIds }: ShoppingListProps) {
  if (noRecipeIds) {
    return (
      <div className="rounded-md border p-4 text-center text-sm text-muted-foreground">
        プランを再生成すると買い物リストが利用できます
      </div>
    )
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">読み込み中...</p>
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="rounded-md border p-4 text-center text-sm text-muted-foreground">
        買い物リストが空です
      </div>
    )
  }

  // カテゴリ別にグループ化
  const grouped: Record<string, typeof data.items> = {}
  for (const item of data.items) {
    const cat = item.category_name || 'その他'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(item)
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {data.recipe_count} レシピ分の食材
      </p>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="space-y-2">
          <h4 className="text-sm font-semibold">{category}</h4>
          <div className="space-y-1">
            {items.map((item, i) => (
              <div key={i} className="flex items-center justify-between rounded-md border px-3 py-2">
                <div>
                  <span className="text-sm font-medium">{item.ingredient_name}</span>
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
      ))}
    </div>
  )
}
