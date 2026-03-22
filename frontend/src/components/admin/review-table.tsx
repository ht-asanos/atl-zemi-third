'use client'

import { useCallback, useEffect, useState } from 'react'
import type { MextFoodSearchItem, ReviewIngredientItem } from '@/types/admin'
import {
  getReviewIngredients,
  updateIngredientMatch,
} from '@/lib/api/admin'
import { ApiError } from '@/lib/api/client'
import { useAuth } from '@/providers/auth-provider'
import MextFoodSearch from './mext-food-search'

export default function ReviewTable() {
  const { session } = useAuth()
  const token = session?.access_token ?? ''

  const [items, setItems] = useState<ReviewIngredientItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTarget, setSearchTarget] = useState<string | null>(null)
  const perPage = 20

  const fetchData = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const res = await getReviewIngredients(token, page, perPage)
      setItems(res.items)
      setTotal(res.total)
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError('管理者権限が必要です')
      } else {
        setError('データの取得に失敗しました')
      }
    } finally {
      setLoading(false)
    }
  }, [token, page])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleApprove = async (item: ReviewIngredientItem) => {
    if (!item.current_mext_food_id) return
    try {
      await updateIngredientMatch(token, item.id, {
        mext_food_id: item.current_mext_food_id,
        approved: true,
      })
      await fetchData()
    } catch {
      setError('更新に失敗しました')
    }
  }

  const handleReject = async (item: ReviewIngredientItem) => {
    try {
      await updateIngredientMatch(token, item.id, {
        mext_food_id: null,
        approved: false,
      })
      await fetchData()
    } catch {
      setError('更新に失敗しました')
    }
  }

  const handleFoodSelect = async (food: MextFoodSearchItem) => {
    if (!searchTarget) return
    try {
      await updateIngredientMatch(token, searchTarget, {
        mext_food_id: food.id,
        approved: true,
      })
      setSearchTarget(null)
      await fetchData()
    } catch {
      setError('更新に失敗しました')
    }
  }

  const totalPages = Math.ceil(total / perPage)

  if (error) {
    return <div className="rounded bg-red-50 p-4 text-red-700">{error}</div>
  }

  if (loading) {
    return <div className="p-4 text-gray-500">読み込み中...</div>
  }

  if (items.length === 0) {
    return <div className="p-4 text-gray-500">レビュー対象の食材はありません</div>
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left">
              <th className="px-3 py-2">レシピ名</th>
              <th className="px-3 py-2">食材名</th>
              <th className="px-3 py-2">現在のマッチ</th>
              <th className="px-3 py-2">信頼度</th>
              <th className="px-3 py-2">アクション</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b hover:bg-gray-50">
                <td className="px-3 py-2">
                  <span>{item.recipe_title}</span>
                  <span
                    className={`ml-2 inline-block rounded-full px-2 py-0.5 text-xs ${
                      item.is_nutrition_calculated
                        ? 'bg-green-100 text-green-700'
                        : 'bg-yellow-100 text-yellow-700'
                    }`}
                  >
                    {item.is_nutrition_calculated ? '計算済み' : '未完了'}
                  </span>
                </td>
                <td className="px-3 py-2">
                  {item.ingredient_name}
                  {item.amount_text && (
                    <span className="ml-1 text-gray-400">
                      ({item.amount_text})
                    </span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {item.current_mext_food_name ?? (
                    <span className="text-gray-400">未マッチ</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {item.match_confidence != null
                    ? `${(item.match_confidence * 100).toFixed(0)}%`
                    : '-'}
                </td>
                <td className="flex gap-1 px-3 py-2">
                  {item.current_mext_food_id && (
                    <button
                      onClick={() => handleApprove(item)}
                      className="rounded bg-green-500 px-2 py-1 text-xs text-white hover:bg-green-600"
                    >
                      承認
                    </button>
                  )}
                  <button
                    onClick={() => handleReject(item)}
                    className="rounded bg-red-500 px-2 py-1 text-xs text-white hover:bg-red-600"
                  >
                    却下
                  </button>
                  <button
                    onClick={() => setSearchTarget(item.id)}
                    className="rounded bg-blue-500 px-2 py-1 text-xs text-white hover:bg-blue-600"
                  >
                    修正
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded border px-3 py-1 disabled:opacity-50"
          >
            前へ
          </button>
          <span className="text-sm text-gray-600">
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded border px-3 py-1 disabled:opacity-50"
          >
            次へ
          </button>
        </div>
      )}

      {searchTarget && (
        <MextFoodSearch
          token={token}
          onSelect={handleFoodSelect}
          onClose={() => setSearchTarget(null)}
        />
      )}
    </>
  )
}
