'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import type { MextFoodSearchItem } from '@/types/admin'
import { searchMextFoods } from '@/lib/api/admin'
import { ApiError } from '@/lib/api/client'

interface Props {
  token: string
  onSelect: (food: MextFoodSearchItem) => void
  onClose: () => void
}

export default function MextFoodSearch({ token, onSelect, onClose }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MextFoodSearchItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const doSearch = useCallback(
    async (q: string) => {
      if (!q.trim()) {
        setResults([])
        return
      }
      setLoading(true)
      setError(null)
      try {
        const res = await searchMextFoods(token, q)
        setResults(res.items)
      } catch (e) {
        if (e instanceof ApiError) {
          setError(e.detail)
        } else {
          setError('検索に失敗しました')
        }
      } finally {
        setLoading(false)
      }
    },
    [token]
  )

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(query), 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, doSearch])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">MEXT 食品検索</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="食品名を入力..."
          className="mb-4 w-full rounded border px-3 py-2"
          autoFocus
        />

        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
        {loading && <p className="mb-2 text-sm text-gray-500">検索中...</p>}

        <div className="max-h-60 overflow-y-auto">
          {results.map((food) => (
            <button
              key={food.id}
              onClick={() => onSelect(food)}
              className="w-full border-b px-3 py-2 text-left hover:bg-gray-50"
            >
              <div className="font-medium">{food.name}</div>
              <div className="text-xs text-gray-500">
                {food.category_name} / {food.kcal_per_100g}kcal /
                P{food.protein_g_per_100g}g (per 100g)
              </div>
            </button>
          ))}
          {!loading && query && results.length === 0 && (
            <p className="py-4 text-center text-sm text-gray-400">
              該当する食品が見つかりません
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
