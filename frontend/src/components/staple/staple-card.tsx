'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { FoodItem } from '@/types/food'

interface StapleCardProps {
  food: FoodItem
  selected: boolean
  onSelect: () => void
}

export function StapleCard({ food, selected, onSelect }: StapleCardProps) {
  return (
    <Card
      className={cn(
        'cursor-pointer transition-colors hover:border-primary',
        selected && 'border-primary bg-primary/5'
      )}
      onClick={onSelect}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{food.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm text-muted-foreground">{food.serving_unit}</p>
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{food.kcal_per_serving} kcal</Badge>
          <Badge variant="outline">{food.price_yen}円</Badge>
          {food.cooking_minutes > 0 && (
            <Badge variant="outline">{food.cooking_minutes}分</Badge>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
