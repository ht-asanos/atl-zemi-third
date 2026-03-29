'use client'

import { useState } from 'react'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { useAuth } from '@/providers/auth-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError } from '@/lib/api/client'
import {
  refreshRecipes,
  backfillRecipes,
  type RefreshResult,
  type BackfillResult,
} from '@/lib/api/recipes'

const ReviewTable = dynamic(
  () => import('@/components/admin/review-table'),
  { ssr: false }
)

export default function AdminReviewPage() {
  const { session } = useAuth()
  const [refreshing, setRefreshing] = useState(false)
  const [backfilling, setBackfilling] = useState(false)
  const [refreshResult, setRefreshResult] = useState<RefreshResult | null>(null)
  const [backfillResult, setBackfillResult] = useState<BackfillResult | null>(null)
  const [error, setError] = useState('')

  const handleRefresh = async () => {
    if (!session?.access_token) return
    setError('')
    setRefreshResult(null)
    setRefreshing(true)
    try {
      const result = await refreshRecipes(session.access_token)
      setRefreshResult(result)
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError('管理者権限が必要です')
      } else {
        setError('レシピ更新に失敗しました')
      }
    } finally {
      setRefreshing(false)
    }
  }

  const handleBackfill = async () => {
    if (!session?.access_token) return
    setError('')
    setBackfillResult(null)
    setBackfilling(true)
    try {
      const result = await backfillRecipes(session.access_token)
      setBackfillResult(result)
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError('管理者権限が必要です')
      } else {
        setError('食材マッチ補完に失敗しました')
      }
    } finally {
      setBackfilling(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">食材マッチング レビュー</h1>
        <div className="flex items-center gap-4">
          <Link href="/admin/training-progressions" className="text-sm text-blue-600 hover:underline">
            Training Progressionsへ
          </Link>
          <Link href="/admin/youtube" className="text-sm text-blue-600 hover:underline">
            YouTube レシピ管理へ
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">レシピ管理</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <Button onClick={handleRefresh} disabled={refreshing}>
              {refreshing ? '更新中...' : 'レシピを更新'}
            </Button>
            <Button variant="outline" onClick={handleBackfill} disabled={backfilling}>
              {backfilling ? '処理中...' : '食材マッチ補完'}
            </Button>
          </div>

          {refreshResult && (
            <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">
              取得: {refreshResult.fetched}件 / 保存: {refreshResult.upserted}件 / エラー: {refreshResult.errors}件
            </div>
          )}

          {backfillResult && (
            <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">
              処理: {backfillResult.processed}件 / マッチ: {backfillResult.matched}件 / エラー: {backfillResult.errors}件
            </div>
          )}
        </CardContent>
      </Card>

      <ReviewTable />
    </div>
  )
}
