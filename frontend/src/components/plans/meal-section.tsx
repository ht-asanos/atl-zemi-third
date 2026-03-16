'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { NutritionStatusBadge } from '@/components/plans/nutrition-status-badge'
import { Separator } from '@/components/ui/separator'
import { Heart } from 'lucide-react'
import { MEAL_INDEX_LABELS, MEAL_TYPE_LABELS } from '@/lib/constants'
import type { MealSuggestion } from '@/types/plan'

interface MealSectionProps {
  meals: MealSuggestion[]
  mealIndex: number
  onChangeRecipe?: () => void
  onToggleFavorite?: (recipeId: string) => void
  favoriteRecipeIds?: Set<string>
}

export function MealSection({ meals, mealIndex, onChangeRecipe, onToggleFavorite, favoriteRecipeIds }: MealSectionProps) {
  const meal = meals[mealIndex]
  if (!meal) return null

  const label = meal.meal_type
    ? MEAL_TYPE_LABELS[meal.meal_type] ?? `食事${mealIndex + 1}`
    : MEAL_INDEX_LABELS[mealIndex] ?? `食事${mealIndex + 1}`

  const hasRecipe = meal.meal_type === 'dinner' && meal.recipe
  const hasProteinSources = meal.protein_sources.length > 0
  const hasBulkItems = meal.bulk_items.length > 0

  const recipeId = meal.recipe?.id
  const isFavorite = recipeId ? (favoriteRecipeIds?.has(recipeId) ?? false) : false
  const recipeNutrition = meal.recipe?.nutrition_per_serving

  return (
    <div className="space-y-2">
      <h4 className="font-semibold">{label}</h4>
      <div className="rounded-md border p-3 space-y-2">
        {hasRecipe ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">レシピ: {meal.recipe!.title}</p>
              <div className="flex items-center gap-1">
                {recipeId && onToggleFavorite && (
                  <button
                    onClick={() => onToggleFavorite(recipeId)}
                    className="hover:scale-110 transition-transform"
                    title={isFavorite ? 'お気に入り解除' : 'お気に入り登録'}
                    aria-label={isFavorite ? 'お気に入り解除' : 'お気に入り登録'}
                    aria-pressed={isFavorite}
                  >
                    <Heart
                      className={`h-5 w-5 ${
                        isFavorite
                          ? 'fill-red-500 text-red-500'
                          : 'text-muted-foreground'
                      }`}
                    />
                  </button>
                )}
                {onChangeRecipe && (
                  <Button variant="outline" size="sm" onClick={onChangeRecipe}>
                    別のレシピ
                  </Button>
                )}
              </div>
            </div>
            {meal.recipe!.image_url && (
              <img
                src={meal.recipe!.image_url}
                alt={meal.recipe!.title}
                className="h-32 w-full rounded-md object-cover"
              />
            )}
            <a
              href={meal.recipe!.recipe_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-sm text-primary underline"
            >
              楽天レシピで見る →
            </a>
            {recipeNutrition && (
              <div className="rounded-md bg-muted/50 p-2">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium text-muted-foreground">食材合算栄養 (1人前)</p>
                  <NutritionStatusBadge status={meal.nutrition_status} warning={meal.nutrition_warning} />
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs">
                  {meal.nutrition_status === 'failed' ? (
                    <>
                      <Badge className="bg-primary/10 text-primary font-medium">-- kcal</Badge>
                      <Badge variant="outline" className="border-blue-200 text-blue-700">P --g</Badge>
                      <Badge variant="outline" className="border-amber-200 text-amber-700">F --g</Badge>
                      <Badge variant="outline" className="border-green-200 text-green-700">C --g</Badge>
                    </>
                  ) : (
                    <>
                      <Badge className="bg-primary/10 text-primary font-medium">{Math.round(recipeNutrition.kcal)} kcal</Badge>
                      <Badge variant="outline" className="border-blue-200 text-blue-700">P {recipeNutrition.protein_g.toFixed(1)}g</Badge>
                      <Badge variant="outline" className="border-amber-200 text-amber-700">F {recipeNutrition.fat_g.toFixed(1)}g</Badge>
                      <Badge variant="outline" className="border-green-200 text-green-700">C {recipeNutrition.carbs_g.toFixed(1)}g</Badge>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm">
            <span className="font-medium">主食:</span> {meal.staple.name} ({meal.staple.serving_unit})
          </p>
        )}
        {hasProteinSources && (
          <p className="text-sm">
            <span className="font-medium">タンパク源:</span>{' '}
            {meal.protein_sources.map((p) => p.name).join(', ')}
          </p>
        )}
        {hasBulkItems && (
          <p className="text-sm">
            <span className="font-medium">かさ増し:</span>{' '}
            {meal.bulk_items.map((b) => b.name).join(', ')}
          </p>
        )}
        <Separator />
        <div className="flex flex-wrap gap-2">
          <Badge className="bg-primary/10 text-primary font-medium">{Math.round(meal.total_kcal)} kcal</Badge>
          <Badge variant="outline" className="border-blue-200 text-blue-700">P {meal.total_protein_g.toFixed(1)}g</Badge>
          <Badge variant="outline" className="border-amber-200 text-amber-700">F {meal.total_fat_g.toFixed(1)}g</Badge>
          <Badge variant="outline" className="border-green-200 text-green-700">C {meal.total_carbs_g.toFixed(1)}g</Badge>
          <Badge variant="outline">{meal.total_price_yen}円</Badge>
          <Badge variant="outline">{meal.total_cooking_minutes}分</Badge>
        </div>
      </div>
    </div>
  )
}
