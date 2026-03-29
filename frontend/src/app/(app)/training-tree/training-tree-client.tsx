'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { TrainingSkillTreeView } from '@/components/training/training-skill-tree-view'
import { Card, CardContent } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { getTrainingSkillTree } from '@/lib/api/plans'
import { ApiError } from '@/lib/api/client'
import { useAuth } from '@/providers/auth-provider'
import type { TrainingEquipment, TrainingSkillTreeResponse } from '@/types/plan'

interface TrainingTreeClientProps {
  startDate: string
  availableEquipment: TrainingEquipment[]
}

export function TrainingTreeClient({ startDate, availableEquipment }: TrainingTreeClientProps) {
  const { session } = useAuth()
  const [data, setData] = useState<TrainingSkillTreeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!session?.access_token) return
    setLoading(true)
    setError('')
    getTrainingSkillTree(session.access_token, startDate, availableEquipment)
      .then((response) => setData(response))
      .catch((e) => {
        if (e instanceof ApiError) {
          setError(e.detail)
          return
        }
        setError('スキルツリーの取得に失敗しました')
      })
      .finally(() => setLoading(false))
  }, [availableEquipment, session?.access_token, startDate])

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Training Skill Tree</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            直近14日の記録とフィードバックから、現在地と次の候補をゲーム風に表示します。
          </p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link href="/daily" className="text-muted-foreground hover:text-foreground">
            今日に戻る
          </Link>
          <Link href="/plans" className="text-muted-foreground hover:text-foreground">
            週間プランへ
          </Link>
        </div>
      </div>

      <Card className="border-dashed">
        <CardContent className="flex flex-wrap gap-4 p-4 text-sm text-muted-foreground">
          <div>基準日: {startDate}</div>
          <div>器具: {availableEquipment.join(', ')}</div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner />
          <p className="ml-2 text-muted-foreground">読み込み中...</p>
        </div>
      ) : error ? (
        <Card>
          <CardContent className="p-8 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : data ? (
        <TrainingSkillTreeView data={data} />
      ) : null}
    </div>
  )
}
