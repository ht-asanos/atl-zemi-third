'use client'

import { useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { TrainingSkillTreeEdge, TrainingSkillTreeNode, TrainingSkillTreeResponse, TrainingSkillTreeTrack } from '@/types/plan'

interface TrainingSkillTreeViewProps {
  data: TrainingSkillTreeResponse
}

const STATUS_LABELS: Record<TrainingSkillTreeNode['status'], string> = {
  locked: '未解放',
  unlocked: '挑戦可能',
  current: '現在地',
  recommended: '次の候補',
  mastered: '突破済み',
  blocked: '負荷注意',
}

const STATUS_NODE_CLASSES: Record<TrainingSkillTreeNode['status'], string> = {
  locked: 'border-slate-300 bg-slate-100 text-slate-500',
  unlocked: 'border-amber-300 bg-amber-50 text-amber-800',
  current: 'border-sky-500 bg-sky-50 text-sky-800 ring-4 ring-sky-100',
  recommended: 'border-emerald-500 bg-emerald-50 text-emerald-800 ring-4 ring-emerald-100 shadow-[0_0_24px_rgba(16,185,129,0.2)]',
  mastered: 'border-violet-500 bg-violet-50 text-violet-800',
  blocked: 'border-rose-500 bg-rose-50 text-rose-800',
}

const STATUS_BADGE_CLASSES: Record<TrainingSkillTreeNode['status'], string> = {
  locked: 'border-slate-300 text-slate-600',
  unlocked: 'border-amber-300 text-amber-700',
  current: 'border-sky-400 text-sky-700',
  recommended: 'border-emerald-400 text-emerald-700',
  mastered: 'border-violet-400 text-violet-700',
  blocked: 'border-rose-400 text-rose-700',
}

function edgeByFrom(track: TrainingSkillTreeTrack, nodeId: string): TrainingSkillTreeEdge | undefined {
  return track.edges.find((edge) => edge.from_exercise_id === nodeId)
}

function goalLabel(goalType: string): string {
  if (goalType === 'strength') return '筋力'
  if (goalType === 'bouldering') return 'ボルダリング'
  return goalType
}

function SummaryCards({ data }: TrainingSkillTreeViewProps) {
  const recommendationCount = data.summary.recommended_count
  const edgeCount = data.summary.available_edge_count

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card className="border-sky-200 bg-sky-50/60">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">現在のツリー</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-slate-700">
          <div>目標: {goalLabel(data.summary.goal_type)}</div>
          <div>進行ルート数: {data.tracks.length}</div>
          <div>登録 edge 数: {edgeCount}</div>
        </CardContent>
      </Card>

      <Card className="border-emerald-200 bg-emerald-50/60">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">次に狙う数</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-slate-700">
          <div>候補ノード: {recommendationCount}</div>
          <div>発光ノードが今週の推奨対象です。</div>
        </CardContent>
      </Card>

      <Card className={cn('border-slate-200', data.summary.has_negative_feedback && 'border-rose-200 bg-rose-50/60')}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">負荷注意</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-slate-700">
          <div>{data.summary.has_negative_feedback ? '最近きつすぎた反応があります。' : '負荷注意ノードはありません。'}</div>
          <div>赤ノードは一度戻すか様子を見る対象です。</div>
        </CardContent>
      </Card>
    </div>
  )
}

function Legend() {
  const statuses: TrainingSkillTreeNode['status'][] = ['current', 'recommended', 'mastered', 'unlocked', 'blocked', 'locked']
  return (
    <div className="flex flex-wrap gap-2">
      {statuses.map((status) => (
        <Badge key={status} variant="outline" className={cn('bg-white', STATUS_BADGE_CLASSES[status])}>
          {STATUS_LABELS[status]}
        </Badge>
      ))}
    </div>
  )
}

function TrackNode({
  node,
  selected,
  onSelect,
}: {
  node: TrainingSkillTreeNode
  selected: boolean
  onSelect: (node: TrainingSkillTreeNode) => void
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(node)}
      className="relative flex w-[220px] shrink-0 flex-col items-center text-left"
    >
      <div
        className={cn(
          'flex h-28 w-28 items-center justify-center rounded-[2rem] border-4 px-4 text-center text-sm font-semibold transition-colors',
          STATUS_NODE_CLASSES[node.status],
          selected && 'ring-4 ring-slate-900/10'
        )}
      >
        {node.name_ja}
      </div>
      <div className="mt-3 w-full rounded-2xl border bg-white/90 p-3 text-left shadow-sm">
        <div className="mb-2 flex items-center justify-between gap-2">
          <Badge variant="outline" className={STATUS_BADGE_CLASSES[node.status]}>
            {STATUS_LABELS[node.status]}
          </Badge>
          <span className="text-xs text-muted-foreground">best {node.best_completed_reps}回</span>
        </div>
        <div className="space-y-1 text-xs text-slate-600">
          <div>必要回数: {node.next_threshold_reps ?? '-'}</div>
          <div>器具: {node.required_equipment.join(', ')}</div>
          {node.recommendation_reason ? (
            <div className="rounded-lg bg-emerald-50 px-2 py-1 text-emerald-800">{node.recommendation_reason}</div>
          ) : null}
        </div>
      </div>
    </button>
  )
}

function TrackLane({
  track,
  selectedNodeId,
  onSelectNode,
}: {
  track: TrainingSkillTreeTrack
  selectedNodeId: string | null
  onSelectNode: (node: TrainingSkillTreeNode) => void
}) {
  return (
    <Card className="overflow-hidden border-slate-200 bg-[linear-gradient(180deg,rgba(248,250,252,0.95),rgba(241,245,249,0.95))]">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-3 text-lg">
          <span>{track.title}</span>
          <Badge variant="outline" className="border-slate-300 text-slate-600">
            {track.nodes.length} ノード
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto pb-2">
          <div className="flex min-w-max items-start gap-0 px-2 py-4">
            {track.nodes.map((node, index) => {
              const outgoing = edgeByFrom(track, node.exercise_id)
              return (
                <div key={node.exercise_id} className="flex items-center">
                  <TrackNode node={node} selected={selectedNodeId === node.exercise_id} onSelect={onSelectNode} />
                  {index < track.nodes.length - 1 && (
                    <div className="flex w-24 shrink-0 flex-col items-center px-2">
                      <div
                        className={cn(
                          'h-1 w-full rounded-full',
                          outgoing?.is_recommended_path ? 'bg-emerald-400' : 'bg-slate-300'
                        )}
                      />
                      {outgoing ? (
                        <div className="mt-2 text-center text-[11px] text-slate-500">
                          {outgoing.from_reps_required}回で次へ
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function flattenNodes(data: TrainingSkillTreeResponse): TrainingSkillTreeNode[] {
  return data.tracks.flatMap((track) => track.nodes)
}

function initialSelectedNode(data: TrainingSkillTreeResponse): TrainingSkillTreeNode | null {
  const nodes = flattenNodes(data)
  return (
    nodes.find((node) => node.status === 'recommended')
    ?? nodes.find((node) => node.status === 'current')
    ?? nodes[0]
    ?? null
  )
}

function DetailPanel({ node }: { node: TrainingSkillTreeNode | null }) {
  if (!node) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          ノードを選ぶと詳細が表示されます。
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-slate-200">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3 text-lg">
          <span>{node.name_ja}</span>
          <Badge variant="outline" className={STATUS_BADGE_CLASSES[node.status]}>
            {STATUS_LABELS[node.status]}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border p-3">
            <div className="text-xs text-muted-foreground">best reps</div>
            <div className="mt-1 text-lg font-semibold">{node.best_completed_reps}回</div>
          </div>
          <div className="rounded-xl border p-3">
            <div className="text-xs text-muted-foreground">次の解放条件</div>
            <div className="mt-1 text-lg font-semibold">{node.next_threshold_reps ?? '-'}回</div>
          </div>
        </div>

        <div className="rounded-xl border p-4">
          <div className="mb-2 text-xs text-muted-foreground">必要器具</div>
          <div>{node.required_equipment.join(', ')}</div>
        </div>

        {node.recommendation_reason ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
            <div className="mb-1 text-xs font-medium uppercase tracking-wide">Recommendation</div>
            <div>{node.recommendation_reason}</div>
          </div>
        ) : null}

        <div className="rounded-xl border p-4">
          <div className="mb-2 text-xs text-muted-foreground">直近ログ</div>
          {node.latest_log_summary ? (
            <div className="space-y-1">
              <div>{node.latest_log_summary.log_date}</div>
              <div>{node.latest_log_summary.sets}セット / {node.latest_log_summary.reps}回</div>
              <div>RPE: {node.latest_log_summary.rpe ?? '-'}</div>
              <div>完了: {node.latest_log_summary.completed ? 'yes' : 'no'}</div>
            </div>
          ) : (
            <div className="text-muted-foreground">まだログがありません。</div>
          )}
        </div>

        <div className="rounded-xl border p-4">
          <div className="mb-2 text-xs text-muted-foreground">直近フィードバック</div>
          {node.latest_feedback_summary ? (
            <div className="space-y-2">
              <div className="text-xs text-muted-foreground">{node.latest_feedback_summary.created_at}</div>
              <div>{node.latest_feedback_summary.source_text}</div>
              <div className="flex flex-wrap gap-2">
                {node.latest_feedback_summary.tags.map((tag) => (
                  <Badge key={tag} variant="outline">{tag}</Badge>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground">まだフィードバックがありません。</div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export function TrainingSkillTreeView({ data }: TrainingSkillTreeViewProps) {
  const [selectedNode, setSelectedNode] = useState<TrainingSkillTreeNode | null>(initialSelectedNode(data))

  const allNodes = useMemo(() => flattenNodes(data), [data])

  useEffect(() => {
    const fallback = initialSelectedNode(data)
    setSelectedNode((prev) => {
      if (!prev) return fallback
      const same = allNodes.find((node) => node.exercise_id === prev.exercise_id)
      return same ?? fallback
    })
  }, [allNodes, data])

  if (data.tracks.length === 0) {
    return (
      <div className="space-y-4">
        <SummaryCards data={data} />
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            まだスキルツリーの元データがありません。管理画面で progression review を進めるとここに表示されます。
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <SummaryCards data={data} />
      <div className="text-sm text-muted-foreground">ノードをクリックすると直近ログとフィードバックを確認できます。</div>
      <Legend />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          {data.tracks.map((track) => (
            <TrackLane
              key={track.track_id}
              track={track}
              selectedNodeId={selectedNode?.exercise_id ?? null}
              onSelectNode={setSelectedNode}
            />
          ))}
        </div>
        <div className="xl:sticky xl:top-6 xl:self-start">
          <DetailPanel node={selectedNode} />
        </div>
      </div>
    </div>
  )
}
