'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AdminTrainingProgressionGraphResponse } from '@/types/admin'

interface AdminTrainingProgressionGraphProps {
  data: AdminTrainingProgressionGraphResponse
}

export function AdminTrainingProgressionGraph({ data }: AdminTrainingProgressionGraphProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">
        <Card><CardContent className="p-4 text-sm">status: {data.summary.status}</CardContent></Card>
        <Card><CardContent className="p-4 text-sm">goal: {data.summary.goal_type}</CardContent></Card>
        <Card><CardContent className="p-4 text-sm">tracks: {data.summary.track_count}</CardContent></Card>
        <Card><CardContent className="p-4 text-sm">unmapped: {data.summary.unmapped_edge_count}</CardContent></Card>
      </div>

      {data.tracks.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            グラフ表示できる edge はありません。
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {data.tracks.map((track) => (
            <Card key={track.track_id} id={`track-${track.track_id}`} className="overflow-hidden">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center justify-between gap-3 text-lg">
                  <span>{track.title}</span>
                  <Badge variant="outline">{track.nodes.length} nodes</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <div className="flex min-w-max items-start gap-0 px-2 py-3">
                    {track.nodes.map((node, index) => {
                      const edge = track.edges.find((item) => item.from_exercise_id === node.exercise_id)
                      return (
                        <div key={node.exercise_id} className="flex items-center">
                          <div className="w-[220px] shrink-0">
                            <div className="rounded-2xl border-2 border-slate-300 bg-slate-50 p-4">
                              <div className="font-semibold">{node.name_ja}</div>
                              <div className="mt-2 text-xs text-muted-foreground">
                                器具: {node.required_equipment.join(', ')}
                              </div>
                              <div className="mt-1 text-xs text-muted-foreground">
                                review count: {node.review_count}
                              </div>
                            </div>
                          </div>
                          {index < track.nodes.length - 1 && (
                            <div className="flex w-40 shrink-0 flex-col items-center px-3">
                              <div className="h-1 w-full rounded-full bg-slate-300" />
                              {edge ? (
                                <div className="mt-2 text-center text-[11px] text-slate-500">
                                  <div>{edge.from_reps_required}回 → {edge.to_reps_target}回</div>
                                  <div className="truncate">{edge.video_title}</div>
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
          ))}
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">未マッピング edge</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.unmapped_edges.length === 0 ? (
            <div className="text-sm text-muted-foreground">未マッピング edge はありません。</div>
          ) : data.unmapped_edges.map((edge) => (
            <div key={edge.edge_id} className="rounded-md border p-3 text-sm">
              <div className="font-medium">{edge.from_label_raw} {edge.from_reps} → {edge.to_label_raw} {edge.to_reps}</div>
              <div className="text-muted-foreground">{edge.video_title} / {edge.video_id}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
