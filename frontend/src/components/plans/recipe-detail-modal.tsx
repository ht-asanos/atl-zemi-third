'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import { Clock, ExternalLink, Heart, Users, X } from 'lucide-react'
import type { RecipeDetail } from '@/types/recipe'

interface RecipeDetailModalProps {
  open: boolean
  recipeId: string | undefined
  isFavorite: boolean
  onClose: () => void
  onToggleFavorite?: (recipeId: string) => void
  fetchRecipeDetail: (recipeId: string) => Promise<RecipeDetail>
}

export function RecipeDetailModal({
  open,
  recipeId,
  isFavorite,
  onClose,
  onToggleFavorite,
  fetchRecipeDetail,
}: RecipeDetailModalProps) {
  const [recipe, setRecipe] = useState<RecipeDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const modalRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<Element | null>(null)

  useEffect(() => {
    if (!open || !recipeId) return

    triggerRef.current = document.activeElement

    const controller = new AbortController()
    let active = true

    setLoading(true)
    setError(null)
    setRecipe(null)

    fetchRecipeDetail(recipeId)
      .then((detail) => {
        if (active) setRecipe(detail)
      })
      .catch((err) => {
        if (active && !controller.signal.aborted) {
          setError(err instanceof Error ? err.message : 'レシピの取得に失敗しました')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [open, recipeId, fetchRecipeDetail])

  // Body scroll lock
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  // Focus close button on open
  useEffect(() => {
    if (open) {
      // Small delay to ensure DOM is ready
      requestAnimationFrame(() => closeButtonRef.current?.focus())
    }
  }, [open, loading])

  // Return focus on close
  useEffect(() => {
    if (!open && triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus()
      triggerRef.current = null
    }
  }, [open])

  // ESC to close
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  // Focus trap
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== 'Tab' || !modalRef.current) return
      const focusable = modalRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    },
    []
  )

  if (!open) return null

  const n = recipe?.nutrition_per_serving
  const coverage = recipe?.ingredient_nutrition_coverage
  const steps = recipe?.generated_steps ?? []
  const sourceFromUrl = /youtu\.be|youtube\.com/.test(recipe?.recipe_url ?? '') ? 'youtube' : 'rakuten'
  const recipeSource = ((recipe?.recipe_source ?? sourceFromUrl) || sourceFromUrl).toLowerCase()
  const resolvedSource = recipeSource === 'youtube' ? 'youtube' : sourceFromUrl
  const sourceLabel = resolvedSource === 'youtube' ? 'YouTube' : '楽天'
  const sourceLinkLabel = resolvedSource === 'youtube' ? 'YouTubeで見る' : '楽天レシピで見る'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="recipe-title"
      onKeyDown={handleKeyDown}
      ref={modalRef}
    >
      <div className="mx-4 w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-xl bg-background shadow-xl">
        {/* Close button */}
        <div className="sticky top-0 z-10 flex justify-end p-2">
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="rounded-full p-1 hover:bg-muted transition-colors"
            aria-label="閉じる"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <Spinner />
            <p className="ml-2 text-sm text-muted-foreground">読み込み中...</p>
          </div>
        )}

        {error && (
          <div className="px-5 pb-5 space-y-3">
            <p className="text-sm text-destructive">{error}</p>
            <button
              onClick={() => {
                if (recipeId) {
                  setLoading(true)
                  setError(null)
                  fetchRecipeDetail(recipeId)
                    .then(setRecipe)
                    .catch((err) =>
                      setError(err instanceof Error ? err.message : 'レシピの取得に失敗しました')
                    )
                    .finally(() => setLoading(false))
                }
              }}
              className="text-sm text-primary underline"
            >
              再試行
            </button>
          </div>
        )}

        {recipe && !loading && (
          <>
            {recipe.image_url && (
              <div className="-mt-2 flex h-72 w-full items-center justify-center overflow-hidden bg-muted/30">
                <img
                  src={recipe.image_url}
                  alt={recipe.title}
                  className="max-h-full max-w-full object-contain"
                />
              </div>
            )}

            <div className="p-5 space-y-4">
              {/* Title + Favorite */}
              <div className="flex items-start justify-between gap-2">
                <h2 id="recipe-title" className="text-lg font-bold">
                  {recipe.title}
                </h2>
                {recipeId && onToggleFavorite && (
                  <button
                    onClick={() => onToggleFavorite(recipeId)}
                    className="shrink-0 hover:scale-110 transition-transform"
                    aria-label={isFavorite ? 'お気に入り解除' : 'お気に入り登録'}
                    aria-pressed={isFavorite}
                  >
                    <Heart
                      className={`h-5 w-5 ${
                        isFavorite ? 'fill-red-500 text-red-500' : 'text-muted-foreground'
                      }`}
                    />
                  </button>
                )}
              </div>

              {/* Tags */}
              {(recipe.tags.length > 0 || recipeSource) && (
                <div className="flex flex-wrap gap-1">
                  <Badge variant="outline" className="text-xs">
                    {sourceLabel}
                  </Badge>
                  {recipe.tags.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}

              {/* Meta: cooking time, servings */}
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                {recipe.cooking_minutes != null && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {recipe.cooking_minutes}分
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Users className="h-4 w-4" />
                  {recipe.servings}人前
                </span>
                {recipe.cost_estimate && (
                  <span>{recipe.cost_estimate}</span>
                )}
              </div>

              {/* Description */}
              {recipe.description && (
                <p className="text-sm text-muted-foreground">{recipe.description}</p>
              )}

              <Separator />

              {/* Ingredients */}
              <div>
                <h3 className="font-semibold mb-2">材料（{recipe.servings}人前）</h3>
                <div className="space-y-1">
                  {recipe.ingredients.map((ing, i) => (
                    <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-border/50 last:border-0 gap-2">
                      <div>
                        <span className="font-medium">{ing.display_ingredient_name || ing.ingredient_name}</span>
                        {!!ing.alternative_ingredient_names?.length && (
                          <p className="text-[11px] text-muted-foreground">
                            候補: {ing.alternative_ingredient_names.join(' / ')}
                          </p>
                        )}
                        {ing.matched_food_name && (
                          <p className="text-[11px] text-muted-foreground">
                            栄養参照: {ing.matched_food_name}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-muted-foreground text-xs">
                        <span>{ing.amount_text ?? '--'}</span>
                        <Badge variant="outline" className="text-[10px] px-1 py-0">
                          {ing.nutrition_match_status === 'matched'
                            ? '紐付け済み'
                            : ing.nutrition_match_status === 'estimated'
                              ? '推定'
                              : '未紐付け'}
                        </Badge>
                        <span>{ing.kcal != null ? `${Math.round(ing.kcal)}kcal` : '--'}</span>
                        <span className="text-blue-600">P{ing.protein_g != null ? ing.protein_g.toFixed(1) : '--'}</span>
                        <span className="text-amber-600">F{ing.fat_g != null ? ing.fat_g.toFixed(1) : '--'}</span>
                        <span className="text-green-600">C{ing.carbs_g != null ? ing.carbs_g.toFixed(1) : '--'}</span>
                      </div>
                    </div>
                  ))}
                  {recipe.ingredients.length === 0 && (
                    <p className="text-sm text-muted-foreground">材料情報がありません</p>
                  )}
                </div>
                {coverage && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    栄養カバー率: {Math.round((coverage.coverage_rate ?? 0) * 100)}%
                    （{coverage.matched_count}/{coverage.total_count}）
                  </p>
                )}
              </div>

              <Separator />

              {/* Generated steps */}
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <h3 className="font-semibold">作り方</h3>
                  <Badge variant="outline">AI提案手順（参考）</Badge>
                </div>
                {steps.length > 0 ? (
                  <ol className="space-y-2">
                    {steps.map((step) => (
                      <li key={step.step_no} className="text-sm">
                        <span className="font-medium">{step.step_no}. </span>
                        {step.text}
                        {step.est_minutes != null && (
                          <span className="ml-2 text-xs text-muted-foreground">約{step.est_minutes}分</span>
                        )}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {recipe.steps_status === 'failed'
                      ? '手順を生成できませんでした。下のリンクから元レシピを確認してください。'
                      : '手順を準備中です。'}
                  </p>
                )}
              </div>

              <Separator />

              {/* Total nutrition per serving */}
              {n && (
                <>
                  <div>
                    <h3 className="font-semibold mb-2">合計栄養（1人前）</h3>
                    <div className="flex flex-wrap gap-2">
                      <Badge className="bg-primary/10 text-primary font-medium">{Math.round(n.kcal)} kcal</Badge>
                      <Badge variant="outline" className="border-blue-200 text-blue-700">P {n.protein_g.toFixed(1)}g</Badge>
                      <Badge variant="outline" className="border-amber-200 text-amber-700">F {n.fat_g.toFixed(1)}g</Badge>
                      <Badge variant="outline" className="border-green-200 text-green-700">C {n.carbs_g.toFixed(1)}g</Badge>
                    </div>
                  </div>
                  <Separator />
                </>
              )}

              {/* External link */}
              <a
                href={recipe.recipe_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm text-primary underline"
              >
                {sourceLinkLabel}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
