'use client'

import { Badge } from '@/components/ui/badge'

interface NutritionStatusBadgeProps {
  status?: 'calculated' | 'estimated' | 'failed' | null
  warning?: string | null
}

export function NutritionStatusBadge({ status, warning }: NutritionStatusBadgeProps) {
  if (!status || status === 'calculated') return null

  if (status === 'failed') {
    return (
      <Badge variant="destructive" title={warning ?? undefined}>
        計算失敗
      </Badge>
    )
  }

  if (status === 'estimated') {
    return (
      <Badge variant="outline" className="border-orange-300 text-orange-600" title={warning ?? undefined}>
        推定値
      </Badge>
    )
  }

  return null
}
