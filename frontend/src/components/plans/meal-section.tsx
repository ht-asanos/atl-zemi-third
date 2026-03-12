'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import type { MealSuggestion } from '@/types/plan'

interface MealSectionProps {
  meals: MealSuggestion[]
  mealIndex: number
  onChangeRecipe?: () => void
  onToggleFavorite?: (recipeId: string) => void
  favoriteRecipeIds?: Set<string>
}

const MEAL_LABELS = ['朝食', '昼食', '夕食']
const MEAL_TYPE_LABELS: Record<string, string> = {
  breakfast: '朝食',
  lunch: '昼食',
  dinner: '夕食',
}

export function MealSection({ meals, mealIndex, onChangeRecipe, onToggleFavorite, favoriteRecipeIds }: MealSectionProps) {
  const meal = meals[mealIndex]
  if (!meal) return null

  const label = meal.meal_type
    ? MEAL_TYPE_LABELS[meal.meal_type] ?? `食事${mealIndex + 1}`
    : MEAL_LABELS[mealIndex] ?? `食事${mealIndex + 1}`

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
                    className="text-lg hover:scale-110 transition-transform"
                    title={isFavorite ? 'お気に入り解除' : 'お気に入り登録'}
                  >
                    {isFavorite ? '\u2764\uFE0F' : '\u2661'}
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
                <p className="text-xs font-medium text-muted-foreground">食材合算栄養 (1人前)</p>
                <div className="mt-1 flex flex-wrap gap-2 text-xs">
                  <Badge variant="secondary">{Math.round(recipeNutrition.kcal)} kcal</Badge>
                  <Badge variant="outline">P {recipeNutrition.protein_g.toFixed(1)}g</Badge>
                  <Badge variant="outline">F {recipeNutrition.fat_g.toFixed(1)}g</Badge>
                  <Badge variant="outline">C {recipeNutrition.carbs_g.toFixed(1)}g</Badge>
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
          <Badge variant="secondary">{Math.round(meal.total_kcal)} kcal</Badge>
          <Badge variant="outline">P {meal.total_protein_g.toFixed(1)}g</Badge>
          <Badge variant="outline">F {meal.total_fat_g.toFixed(1)}g</Badge>
          <Badge variant="outline">C {meal.total_carbs_g.toFixed(1)}g</Badge>
          <Badge variant="outline">{meal.total_price_yen}円</Badge>
          <Badge variant="outline">{meal.total_cooking_minutes}分</Badge>
        </div>
      </div>
    </div>
  )
}
