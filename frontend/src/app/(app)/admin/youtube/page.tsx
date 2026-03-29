'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/providers/auth-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { RecipeDetailModal } from '@/components/plans/recipe-detail-modal'
import { ApiError } from '@/lib/api/client'
import { getRecipe } from '@/lib/api/recipes'
import {
  batchAdaptYoutubeRecipes,
  extractYoutubeRecipe,
  registerYoutubeRecipe,
  listYoutubeRecipes,
  type BatchAdaptResponse,
  type RecipeDraft,
  type RecipeDraftIngredient,
  type RecipeDraftStep,
  type YoutubeExtractResponse,
  type YoutubeRecipeItem,
} from '@/lib/api/admin'
import { ExternalLink } from 'lucide-react'

export default function AdminYoutubePage() {
  const { session } = useAuth()

  // Section 1: URL input
  const [url, setUrl] = useState('')
  const [stapleName, setStapleName] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [extractResult, setExtractResult] = useState<YoutubeExtractResponse | null>(null)

  // Section 2: Recipe edit
  const [draft, setDraft] = useState<RecipeDraft | null>(null)
  const [videoId, setVideoId] = useState('')
  const [registering, setRegistering] = useState(false)
  const [registerSuccess, setRegisterSuccess] = useState('')

  // Section 3: Batch adapt
  const [batchChannelHandle, setBatchChannelHandle] = useState('@yugetube2020')
  const [batchSourceQuery, setBatchSourceQuery] = useState('パスタ')
  const [batchTargetStaple, setBatchTargetStaple] = useState('冷凍うどん')
  const [batchMaxResults, setBatchMaxResults] = useState(10)
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchResult, setBatchResult] = useState<BatchAdaptResponse | null>(null)

  // Section 4: Recipe list
  const [recipes, setRecipes] = useState<YoutubeRecipeItem[]>([])
  const [listTotal, setListTotal] = useState(0)
  const [listPage, setListPage] = useState(1)
  const [selectedRecipeId, setSelectedRecipeId] = useState<string | undefined>(undefined)
  const [detailOpen, setDetailOpen] = useState(false)

  const [error, setError] = useState('')

  const token = session?.access_token

  const loadRecipes = useCallback(async (page: number) => {
    if (!token) return
    try {
      const res = await listYoutubeRecipes(token, page)
      setRecipes(res.items)
      setListTotal(res.total)
      setListPage(res.page)
    } catch {
      // silent
    }
  }, [token])

  useEffect(() => {
    loadRecipes(1)
  }, [loadRecipes])

  const handleExtract = async () => {
    if (!token || !url.trim()) return
    setError('')
    setExtractResult(null)
    setDraft(null)
    setRegisterSuccess('')
    setExtracting(true)
    try {
      const result = await extractYoutubeRecipe(token, url, stapleName || undefined)
      setExtractResult(result)
      setDraft(result.recipe_draft)
      setVideoId(result.video_id)
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.detail)
      } else {
        setError('レシピ抽出に失敗しました')
      }
    } finally {
      setExtracting(false)
    }
  }

  const handleRegister = async () => {
    if (!token || !draft || !videoId) return
    setError('')
    setRegisterSuccess('')
    setRegistering(true)
    try {
      const result = await registerYoutubeRecipe(token, videoId, draft)
      setRegisterSuccess(`「${result.title}」を登録しました（栄養: ${result.nutrition_status}）`)
      await loadRecipes(1)
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.detail)
      } else {
        setError('レシピ登録に失敗しました')
      }
    } finally {
      setRegistering(false)
    }
  }

  const handleBatchAdapt = async () => {
    if (!token || !batchChannelHandle.trim() || !batchSourceQuery.trim()) return
    setError('')
    setRegisterSuccess('')
    setBatchResult(null)
    setBatchRunning(true)
    try {
      const result = await batchAdaptYoutubeRecipes(token, {
        channel_handle: batchChannelHandle.trim(),
        source_query: batchSourceQuery.trim(),
        target_staple: batchTargetStaple,
        max_results: batchMaxResults,
      })
      setBatchResult(result)
      await loadRecipes(1)
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.detail)
      } else {
        setError('一括アレンジに失敗しました')
      }
    } finally {
      setBatchRunning(false)
    }
  }

  const updateDraftField = <K extends keyof RecipeDraft>(key: K, value: RecipeDraft[K]) => {
    if (!draft) return
    setDraft({ ...draft, [key]: value })
  }

  const updateIngredient = (index: number, field: keyof RecipeDraftIngredient, value: string | null) => {
    if (!draft) return
    const updated = [...draft.ingredients]
    updated[index] = { ...updated[index], [field]: value }
    setDraft({ ...draft, ingredients: updated })
  }

  const addIngredient = () => {
    if (!draft) return
    setDraft({
      ...draft,
      ingredients: [...draft.ingredients, { ingredient_name: '', amount_text: null }],
    })
  }

  const removeIngredient = (index: number) => {
    if (!draft) return
    setDraft({ ...draft, ingredients: draft.ingredients.filter((_, i) => i !== index) })
  }

  const updateStep = (index: number, field: keyof RecipeDraftStep, value: string | number | null) => {
    if (!draft) return
    const updated = [...draft.steps]
    updated[index] = { ...updated[index], [field]: value }
    setDraft({ ...draft, steps: updated })
  }

  const addStep = () => {
    if (!draft) return
    const nextNo = draft.steps.length > 0 ? Math.max(...draft.steps.map(s => s.step_no)) + 1 : 1
    setDraft({
      ...draft,
      steps: [...draft.steps, { step_no: nextNo, text: '', est_minutes: null }],
    })
  }

  const removeStep = (index: number) => {
    if (!draft) return
    setDraft({ ...draft, steps: draft.steps.filter((_, i) => i !== index) })
  }

  const perPage = 20
  const totalPages = Math.ceil(listTotal / perPage)

  const fetchRecipeDetail = useCallback(async (recipeId: string) => {
    if (!token) throw new Error('認証が必要です')
    return getRecipe(token, recipeId)
  }, [token])

  const openRecipeDetail = (recipeId: string) => {
    setSelectedRecipeId(recipeId)
    setDetailOpen(true)
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">YouTube レシピ管理</h1>
        <div className="flex items-center gap-4">
          <Link href="/admin/training-progressions" className="text-sm text-blue-600 hover:underline">
            Training Progressionsへ
          </Link>
          <Link href="/admin/review" className="text-sm text-blue-600 hover:underline">
            食材レビューへ
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {registerSuccess && (
        <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700">{registerSuccess}</div>
      )}

      {/* Section 1: URL Input */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">YouTube URL からレシピ抽出</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium">YouTube URL</label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">主食名（オプション）</label>
            <input
              type="text"
              value={stapleName}
              onChange={(e) => setStapleName(e.target.value)}
              placeholder="例: 冷凍うどん"
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
          </div>
          <Button onClick={handleExtract} disabled={extracting || !url.trim()}>
            {extracting ? '抽出中...（30秒程度かかります）' : '字幕取得・レシピ抽出'}
          </Button>
        </CardContent>
      </Card>

      {/* Section 2: Recipe Preview/Edit */}
      {draft && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">レシピプレビュー・編集</CardTitle>
            {extractResult && (
              <div className="mt-2 flex gap-2">
                <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                  品質スコア: {(extractResult.transcript_quality as Record<string, number>).quality_score ?? '-'}
                </span>
                <span className="inline-block rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                  video_id: {videoId}
                </span>
              </div>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Basic fields */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium">タイトル</label>
                <input
                  type="text"
                  value={draft.title}
                  onChange={(e) => updateDraftField('title', e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">人数</label>
                <input
                  type="number"
                  value={draft.servings}
                  onChange={(e) => updateDraftField('servings', parseInt(e.target.value) || 2)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">調理時間（分）</label>
                <input
                  type="number"
                  value={draft.cooking_minutes ?? ''}
                  onChange={(e) => updateDraftField('cooking_minutes', e.target.value ? parseInt(e.target.value) : null)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
            </div>

            {/* Ingredients */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-medium">材料</h3>
                <Button variant="outline" size="sm" onClick={addIngredient}>追加</Button>
              </div>
              <div className="space-y-2">
                {draft.ingredients.map((ing, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={ing.ingredient_name}
                      onChange={(e) => updateIngredient(i, 'ingredient_name', e.target.value)}
                      placeholder="食材名"
                      className="flex-1 rounded-md border px-3 py-1.5 text-sm"
                    />
                    <input
                      type="text"
                      value={ing.amount_text ?? ''}
                      onChange={(e) => updateIngredient(i, 'amount_text', e.target.value || null)}
                      placeholder="分量"
                      className="w-28 rounded-md border px-3 py-1.5 text-sm"
                    />
                    <button
                      onClick={() => removeIngredient(i)}
                      className="text-sm text-red-500 hover:text-red-700"
                    >
                      削除
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Steps */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-medium">手順</h3>
                <Button variant="outline" size="sm" onClick={addStep}>追加</Button>
              </div>
              <div className="space-y-2">
                {draft.steps.map((step, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="mt-2 text-sm font-medium text-gray-500">{step.step_no}.</span>
                    <textarea
                      value={step.text}
                      onChange={(e) => updateStep(i, 'text', e.target.value)}
                      placeholder="手順の説明"
                      rows={2}
                      className="flex-1 rounded-md border px-3 py-1.5 text-sm"
                    />
                    <input
                      type="number"
                      value={step.est_minutes ?? ''}
                      onChange={(e) => updateStep(i, 'est_minutes', e.target.value ? parseInt(e.target.value) : null)}
                      placeholder="分"
                      className="w-16 rounded-md border px-3 py-1.5 text-sm"
                    />
                    <button
                      onClick={() => removeStep(i)}
                      className="text-sm text-red-500 hover:text-red-700"
                    >
                      削除
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <Button onClick={handleRegister} disabled={registering}>
              {registering ? '登録中...' : 'DB に登録'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Section 3: Batch Adapt */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">主食アレンジ一括登録</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium">チャンネルハンドル</label>
              <input
                type="text"
                value={batchChannelHandle}
                onChange={(e) => setBatchChannelHandle(e.target.value)}
                placeholder="@yugetube2020"
                className="w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">元動画の検索語</label>
              <input
                type="text"
                value={batchSourceQuery}
                onChange={(e) => setBatchSourceQuery(e.target.value)}
                placeholder="例: パスタ"
                className="w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">変換先主食</label>
              <Select
                value={batchTargetStaple}
                onChange={(e) => setBatchTargetStaple(e.target.value)}
                className="w-full"
              >
                <option value="冷凍うどん">冷凍うどん</option>
                <option value="白米">白米</option>
                <option value="オートミール">オートミール</option>
                <option value="パスタ">パスタ</option>
                <option value="食パン">食パン</option>
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">処理件数</label>
              <input
                type="number"
                min={1}
                max={10}
                value={batchMaxResults}
                onChange={(e) => setBatchMaxResults(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
                className="w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              onClick={handleBatchAdapt}
              disabled={batchRunning || !batchChannelHandle.trim() || !batchSourceQuery.trim()}
            >
              {batchRunning ? '一括アレンジ実行中...' : '一括アレンジ実行'}
            </Button>
            <p className="text-xs text-muted-foreground">
              `filtered_source_mismatch` と `filtered_non_meal` は登録されません
            </p>
          </div>

          {batchResult && (
            <div className="space-y-3 rounded-md border p-4">
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
                <div>
                  <div className="text-xs text-muted-foreground">videos_found</div>
                  <div className="font-medium">{batchResult.videos_found}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">processed</div>
                  <div className="font-medium">{batchResult.videos_processed}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">success</div>
                  <div className="font-medium text-green-700">{batchResult.succeeded}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">failed</div>
                  <div className="font-medium text-red-700">{batchResult.failed}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">skipped</div>
                  <div className="font-medium text-amber-700">{batchResult.skipped}</div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="pb-2 pr-4">元動画タイトル</th>
                      <th className="pb-2 pr-4">status</th>
                      <th className="pb-2 pr-4">生成レシピ</th>
                      <th className="pb-2">error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchResult.results.map((item) => {
                      const resultRecipeId = item.recipe_id
                      return (
                      <tr key={item.video_id} className="border-b last:border-0 align-top">
                        <td className="py-2 pr-4">{item.video_title}</td>
                        <td className="py-2 pr-4">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                            item.status === 'success'
                              ? 'bg-green-100 text-green-700'
                              : item.status === 'skipped_existing' || item.status.startsWith('filtered_')
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-red-100 text-red-700'
                          }`}>
                            {item.status}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          {resultRecipeId !== null && item.recipe_title ? (
                            <button
                              type="button"
                              onClick={() => openRecipeDetail(resultRecipeId)}
                              className="text-left text-blue-600 hover:underline"
                            >
                              {item.recipe_title}
                            </button>
                          ) : (
                            '-'
                          )}
                        </td>
                        <td className="py-2 text-xs text-muted-foreground whitespace-pre-wrap">
                          {item.error || '-'}
                        </td>
                      </tr>
                    )})}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section 4: Registered Recipe List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">登録済み YouTube レシピ</CardTitle>
        </CardHeader>
        <CardContent>
          {recipes.length === 0 ? (
            <p className="text-sm text-muted-foreground">登録済みレシピはありません</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="pb-2 pr-4">タイトル</th>
                      <th className="pb-2 pr-4">Video ID</th>
                      <th className="pb-2 pr-4">栄養</th>
                      <th className="pb-2 pr-4">手順</th>
                      <th className="pb-2">作成日</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recipes.map((recipe) => (
                      <tr key={recipe.id} className="border-b last:border-0">
                        <td className="py-2 pr-4">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => openRecipeDetail(recipe.id)}
                              className="text-left text-blue-600 hover:underline"
                            >
                              {recipe.title}
                            </button>
                            {recipe.youtube_video_id && (
                              <a
                                href={`https://www.youtube.com/watch?v=${recipe.youtube_video_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center text-xs text-muted-foreground hover:text-foreground"
                                title="YouTube で開く"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                              </a>
                            )}
                          </div>
                        </td>
                        <td className="py-2 pr-4 font-mono text-xs">
                          {recipe.youtube_video_id ?? '-'}
                        </td>
                        <td className="py-2 pr-4">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                            recipe.nutrition_status === 'calculated'
                              ? 'bg-green-100 text-green-700'
                              : recipe.nutrition_status === 'estimated'
                                ? 'bg-yellow-100 text-yellow-700'
                                : 'bg-gray-100 text-gray-600'
                          }`}>
                            {recipe.nutrition_status ?? '-'}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                            recipe.steps_status === 'generated'
                              ? 'bg-green-100 text-green-700'
                              : 'bg-gray-100 text-gray-600'
                          }`}>
                            {recipe.steps_status ?? '-'}
                          </span>
                        </td>
                        <td className="py-2 text-xs text-gray-500">
                          {recipe.created_at ? new Date(recipe.created_at).toLocaleDateString('ja-JP') : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={listPage <= 1}
                    onClick={() => loadRecipes(listPage - 1)}
                  >
                    前へ
                  </Button>
                  <span className="text-sm text-gray-600">
                    {listPage} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={listPage >= totalPages}
                    onClick={() => loadRecipes(listPage + 1)}
                  >
                    次へ
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <RecipeDetailModal
        open={detailOpen}
        recipeId={selectedRecipeId}
        isFavorite={false}
        onClose={() => setDetailOpen(false)}
        fetchRecipeDetail={fetchRecipeDetail}
      />
    </div>
  )
}
