'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/providers/auth-provider'
import { AdminTrainingProgressionGraph } from '@/components/training/admin-training-progression-graph'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError } from '@/lib/api/client'
import {
  applyTrainingProgressionPresets,
  getTrainingProgressionGraph,
  ingestTrainingProgressions,
  listTrainingProgressionCatalog,
  listTrainingProgressionReview,
  listTrainingProgressionSources,
  reviewTrainingProgression,
} from '@/lib/api/admin'
import type { Exercise } from '@/types/plan'
import type {
  AdminTrainingProgressionGraphResponse,
  TrainingProgressionIngestResponse,
  TrainingProgressionPresetReview,
  TrainingProgressionReviewActionRequest,
  TrainingProgressionReviewItem,
  TrainingProgressionSourceExtractionPayload,
  TrainingProgressionSourceItem,
} from '@/types/admin'

type ReviewStatus = 'pending' | 'approved' | 'rejected'
type SourceFilter = 'all' | 'review_pending' | 'extracted_no_edges' | 'failed' | 'no_transcript'

type ReviewFormState = {
  from_exercise_id: string
  from_reps: number
  to_exercise_id: string
  to_reps: number
  goal_scope: string
  review_note: string
  add_aliases: string
}

type IngestFormState = {
  channel_handle: string
  title_keyword: string
  max_results: number
}

function parseSourceExtractionPayload(raw: unknown): TrainingProgressionSourceExtractionPayload | null {
  if (!raw) return null
  if (Array.isArray(raw)) {
    return { edges: raw.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object') }
  }
  if (typeof raw === 'object') {
    return raw as TrainingProgressionSourceExtractionPayload
  }
  return null
}

function getSourceQualityScore(source: TrainingProgressionSourceItem): number | null {
  const raw = source.transcript_quality_json?.['quality_score']
  return typeof raw === 'number' ? raw : null
}

function getNaturalizationLabel(source: TrainingProgressionSourceItem): string {
  const payload = parseSourceExtractionPayload(source.raw_extraction_json)
  const reason = payload?.diagnostics?.naturalization_reason
  if (!payload?.diagnostics?.naturalization_applied) return 'off'
  if (reason === 'auto_generated') return 'auto_generated'
  if (reason === 'low_quality') return 'low_quality'
  return 'applied'
}

function getExtractionCount(source: TrainingProgressionSourceItem): number {
  const payload = parseSourceExtractionPayload(source.raw_extraction_json)
  if (typeof payload?.diagnostics?.extraction_count === 'number') {
    return payload.diagnostics.extraction_count
  }
  return Array.isArray(payload?.edges) ? payload.edges.length : 0
}

function matchesSourceFilter(source: TrainingProgressionSourceItem, filter: SourceFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'review_pending') return source.ingest_status === 'review_pending'
  if (filter === 'failed') return source.ingest_status === 'failed'
  if (filter === 'no_transcript') return source.ingest_status === 'no_transcript'
  if (filter === 'extracted_no_edges') {
    return source.ingest_status === 'extracted' && getExtractionCount(source) === 0
  }
  return true
}

function buildFormState(item: TrainingProgressionReviewItem, preset?: TrainingProgressionPresetReview | null): ReviewFormState {
  return {
    from_exercise_id: preset?.from_exercise_id ?? item.edge.from_exercise_id ?? '',
    from_reps: preset?.from_reps ?? item.edge.from_reps,
    to_exercise_id: preset?.to_exercise_id ?? item.edge.to_exercise_id ?? '',
    to_reps: preset?.to_reps ?? item.edge.to_reps,
    goal_scope: (preset?.goal_scope ?? item.edge.goal_scope ?? []).join(','),
    review_note: preset?.review_note ?? item.edge.review_note ?? '',
    add_aliases: (preset?.add_aliases ?? []).join(','),
  }
}

function SourceDetail({ source }: { source: TrainingProgressionSourceItem }) {
  const payload = parseSourceExtractionPayload(source.raw_extraction_json)
  const diagnostics = payload?.diagnostics
  const edges = payload?.edges ?? []
  const transcriptOriginalPreview = diagnostics?.transcript_original_preview
  const transcriptNaturalizedPreview = diagnostics?.transcript_naturalized_preview

  return (
    <div className="mt-3 space-y-3 rounded-md border bg-muted/30 p-3 text-xs">
      <div className="grid gap-2 md:grid-cols-2">
        <div>platform: {source.platform}</div>
        <div>channel: {source.channel_handle}</div>
        <div>query: {source.title_query ?? '-'}</div>
        <div>language: {source.transcript_language ?? '-'}</div>
        <div>quality_score: {getSourceQualityScore(source) ?? '-'}</div>
        <div>naturalize: {getNaturalizationLabel(source)}</div>
        <div>extractor_model: {diagnostics?.extractor_model ?? '-'}</div>
        <div>extraction_count: {getExtractionCount(source)}</div>
        <div>empty_reason_hint: {diagnostics?.empty_reason_hint ?? '-'}</div>
        <div>transcript_changed: {diagnostics?.transcript_changed ? 'yes' : 'no'}</div>
      </div>

      {payload?.error && (
        <div className="rounded bg-destructive/10 px-3 py-2 text-destructive">
          extraction error: {payload.error}
        </div>
      )}

      {transcriptOriginalPreview && (
        <div>
          <div className="mb-1 font-medium">transcript_original_preview</div>
          <pre className="whitespace-pre-wrap rounded bg-background p-3">{transcriptOriginalPreview}</pre>
        </div>
      )}

      {transcriptNaturalizedPreview && (
        <div>
          <div className="mb-1 font-medium">transcript_naturalized_preview</div>
          <pre className="whitespace-pre-wrap rounded bg-background p-3">{transcriptNaturalizedPreview}</pre>
        </div>
      )}

      <div>
        <div className="mb-1 font-medium">extracted_edges</div>
        <pre className="overflow-x-auto rounded bg-background p-3">{JSON.stringify(edges, null, 2)}</pre>
      </div>
    </div>
  )
}

export default function AdminTrainingProgressionsPage() {
  const { session } = useAuth()
  const token = session?.access_token
  const [status, setStatus] = useState<ReviewStatus>('pending')
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')
  const [sourceLimit, setSourceLimit] = useState(50)
  const [expandedSourceId, setExpandedSourceId] = useState<string | null>(null)
  const [items, setItems] = useState<TrainingProgressionReviewItem[]>([])
  const [sources, setSources] = useState<TrainingProgressionSourceItem[]>([])
  const [catalog, setCatalog] = useState<Exercise[]>([])
  const [graph, setGraph] = useState<AdminTrainingProgressionGraphResponse | null>(null)
  const [graphGoalType, setGraphGoalType] = useState<'all' | 'strength' | 'bouldering'>('all')
  const [forms, setForms] = useState<Record<string, ReviewFormState>>({})
  const [loading, setLoading] = useState(true)
  const [savingEdgeId, setSavingEdgeId] = useState<string | null>(null)
  const [applyingPresets, setApplyingPresets] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [ingestForm, setIngestForm] = useState<IngestFormState>({
    channel_handle: '@CalisthenicsTokyo',
    title_keyword: 'ができるなら',
    max_results: 25,
  })
  const [ingestResult, setIngestResult] = useState<TrainingProgressionIngestResponse | null>(null)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      const [reviewRes, sourceRes] = await Promise.all([
        listTrainingProgressionReview(token, status, 100),
        listTrainingProgressionSources(token, sourceLimit),
      ])
      setItems(reviewRes.items)
      setSources(sourceRes.items)
      setForms(
        Object.fromEntries(
          reviewRes.items.map((item) => [item.edge.id, buildFormState(item, item.preset_review)])
        )
      )
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.detail)
      } else {
        setError('progression review の取得に失敗しました')
      }
    } finally {
      setLoading(false)
    }
  }, [sourceLimit, status, token])

  useEffect(() => {
    if (!token) return
    listTrainingProgressionCatalog(token)
      .then((catalogItems) => setCatalog(catalogItems))
      .catch(() => setCatalog([]))
  }, [token])

  useEffect(() => {
    if (!token) return
    getTrainingProgressionGraph(token, status === 'pending' ? 'pending' : status, graphGoalType, 200)
      .then((response) => setGraph(response))
      .catch(() => setGraph(null))
  }, [graphGoalType, status, token])

  useEffect(() => {
    void load()
  }, [load])

  const pendingPresetCount = useMemo(
    () => items.filter((item) => item.preset_review != null).length,
    [items]
  )

  const filteredSources = useMemo(
    () => sources.filter((source) => matchesSourceFilter(source, sourceFilter)),
    [sourceFilter, sources]
  )

  const sourceCounts = useMemo(() => ({
    all: sources.length,
    review_pending: sources.filter((source) => matchesSourceFilter(source, 'review_pending')).length,
    extracted_no_edges: sources.filter((source) => matchesSourceFilter(source, 'extracted_no_edges')).length,
    failed: sources.filter((source) => matchesSourceFilter(source, 'failed')).length,
    no_transcript: sources.filter((source) => matchesSourceFilter(source, 'no_transcript')).length,
  }), [sources])

  const updateForm = (edgeId: string, patch: Partial<ReviewFormState>) => {
    setForms((prev) => ({
      ...prev,
      [edgeId]: { ...prev[edgeId], ...patch },
    }))
  }

  const fillPreset = (item: TrainingProgressionReviewItem) => {
    if (!item.preset_review) return
    setForms((prev) => ({
      ...prev,
      [item.edge.id]: buildFormState(item, item.preset_review),
    }))
  }

  const jumpToSource = (sourceId: string | null | undefined) => {
    if (!sourceId) return
    setExpandedSourceId(sourceId)
    requestAnimationFrame(() => {
      const element = document.getElementById(`source-${sourceId}`)
      element?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  const submitReview = async (item: TrainingProgressionReviewItem, reviewStatus: 'approved' | 'rejected') => {
    if (!token) return
    const form = forms[item.edge.id]
    if (!form) return
    setSavingEdgeId(item.edge.id)
    setError('')
    setNotice('')
    try {
      const body: TrainingProgressionReviewActionRequest = {
        review_status: reviewStatus,
        from_exercise_id: form.from_exercise_id || null,
        from_reps: form.from_reps || null,
        to_exercise_id: form.to_exercise_id || null,
        to_reps: form.to_reps || null,
        goal_scope: form.goal_scope
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
        review_note: form.review_note || null,
        add_aliases: form.add_aliases
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
      }
      await reviewTrainingProgression(token, item.edge.id, body)
      setNotice(`edge ${item.edge.id.slice(0, 8)} を ${reviewStatus} に更新しました`)
      await load()
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.detail)
      } else {
        setError('review の保存に失敗しました')
      }
    } finally {
      setSavingEdgeId(null)
    }
  }

  const handleApplyPresets = async () => {
    if (!token) return
    setApplyingPresets(true)
    setError('')
    setNotice('')
    try {
      const result = await applyTrainingProgressionPresets(token)
      setNotice(`preset 適用: reviewed=${result.reviewed}, skipped=${result.skipped}`)
      await load()
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.detail)
      } else {
        setError('preset 適用に失敗しました')
      }
    } finally {
      setApplyingPresets(false)
    }
  }

  const handleIngest = async () => {
    if (!token) return
    setIngesting(true)
    setError('')
    setNotice('')
    try {
      const response = await ingestTrainingProgressions(token, ingestForm)
      setIngestResult(response)
      setNotice(
        `ingest 完了: scanned=${response.videos_scanned}, title_matched=${response.videos_title_matched}, with_edges=${response.videos_with_edges}`
      )
      setSourceFilter('all')
      if (response.results[0]?.source_id) {
        setExpandedSourceId(response.results[0].source_id)
      }
      await load()
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.detail)
      } else {
        setError('training progression ingest に失敗しました')
      }
    } finally {
      setIngesting(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Training Progressions</h1>
        <div className="flex items-center gap-4">
          <Link href="/admin/youtube" className="text-sm text-blue-600 hover:underline">
            YouTube レシピ管理へ
          </Link>
          <Link href="/admin/review" className="text-sm text-blue-600 hover:underline">
            食材レビューへ
          </Link>
        </div>
      </div>

      {error && <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      {notice && <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700">{notice}</div>}

      <div className="mb-6 grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Training progression ingest</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium">channel_handle</label>
                <input
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={ingestForm.channel_handle}
                  onChange={(e) => setIngestForm((prev) => ({ ...prev, channel_handle: e.target.value }))}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">title_keyword</label>
                <input
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={ingestForm.title_keyword}
                  onChange={(e) => setIngestForm((prev) => ({ ...prev, title_keyword: e.target.value }))}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">max_results</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={ingestForm.max_results}
                  onChange={(e) => setIngestForm((prev) => ({ ...prev, max_results: Math.max(1, parseInt(e.target.value, 10) || 1) }))}
                />
              </div>
            </div>

            <Button onClick={handleIngest} disabled={ingesting || !token}>
              {ingesting ? 'ingest 実行中...' : 'ingest を実行'}
            </Button>

            {ingestResult && (
              <div className="space-y-4 rounded-md border p-4 text-sm">
                <div className="grid gap-3 md:grid-cols-4">
                  <div><div className="text-xs text-muted-foreground">videos_scanned</div><div className="font-medium">{ingestResult.videos_scanned}</div></div>
                  <div><div className="text-xs text-muted-foreground">videos_title_matched</div><div className="font-medium">{ingestResult.videos_title_matched}</div></div>
                  <div><div className="text-xs text-muted-foreground">videos_found</div><div className="font-medium">{ingestResult.videos_found}</div></div>
                  <div><div className="text-xs text-muted-foreground">videos_processed</div><div className="font-medium">{ingestResult.videos_processed}</div></div>
                  <div><div className="text-xs text-muted-foreground">transcripts_fetched</div><div className="font-medium">{ingestResult.transcripts_fetched}</div></div>
                  <div><div className="text-xs text-muted-foreground">transcripts_naturalized</div><div className="font-medium">{ingestResult.transcripts_naturalized}</div></div>
                  <div><div className="text-xs text-muted-foreground">videos_with_edges</div><div className="font-medium">{ingestResult.videos_with_edges}</div></div>
                  <div><div className="text-xs text-muted-foreground">edges_created</div><div className="font-medium">{ingestResult.edges_created}</div></div>
                </div>

                <div className="space-y-2">
                  {ingestResult.results.map((result) => (
                    <div key={`${result.video_id}-${result.status}`} className="flex flex-col gap-2 rounded-md border p-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <div className="font-medium">{result.video_title}</div>
                        <div className="text-xs text-muted-foreground">
                          {result.video_id} / {result.status} / edges={result.edges_created}
                        </div>
                        {result.error && <div className="text-xs text-destructive">{result.error}</div>}
                      </div>
                      {result.source_id && (
                        <Button variant="outline" size="sm" onClick={() => jumpToSource(result.source_id)}>
                          source を表示
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Pending preset を一括反映</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              現在表示中の {status} edge のうち、curated preset に一致するものを自動承認します。
            </p>
            <div className="text-sm text-muted-foreground">
              preset 対象数: {pendingPresetCount} / 表示件数: {items.length}
            </div>
            <Button onClick={handleApplyPresets} disabled={applyingPresets || !token}>
              {applyingPresets ? '適用中...' : '既知の progression preset を適用'}
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-sm font-medium">Source filter</div>
          {([
            ['all', `all (${sourceCounts.all})`],
            ['review_pending', `review_pending (${sourceCounts.review_pending})`],
            ['extracted_no_edges', `extracted_no_edges (${sourceCounts.extracted_no_edges})`],
            ['failed', `failed (${sourceCounts.failed})`],
            ['no_transcript', `no_transcript (${sourceCounts.no_transcript})`],
          ] as Array<[SourceFilter, string]>).map(([candidate, label]) => (
            <Button
              key={candidate}
              variant={sourceFilter === candidate ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSourceFilter(candidate)}
            >
              {label}
            </Button>
          ))}
          <div className="ml-auto flex items-center gap-2 text-sm">
            <label htmlFor="source-limit">source limit</label>
            <select
              id="source-limit"
              className="rounded-md border px-2 py-1"
              value={sourceLimit}
              onChange={(e) => setSourceLimit(parseInt(e.target.value, 10))}
            >
              {[20, 50, 100].map((limit) => (
                <option key={limit} value={limit}>{limit}</option>
              ))}
            </select>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">最新 source</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {filteredSources.length === 0 ? (
              <div className="rounded-md border p-4 text-sm text-muted-foreground">該当 source はありません</div>
            ) : filteredSources.map((source) => {
              const payload = parseSourceExtractionPayload(source.raw_extraction_json)
              const qualityScore = getSourceQualityScore(source)
              const extractionCount = getExtractionCount(source)
              const naturalizationLabel = getNaturalizationLabel(source)
              const emptyReason = payload?.diagnostics?.empty_reason_hint
              const transcriptPreview = payload?.diagnostics?.transcript_naturalized_preview
              const isExpanded = expandedSourceId === source.id

              return (
                <div key={source.id} id={`source-${source.id}`} className="rounded-md border p-3 text-sm">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{source.video_title}</div>
                      <div className="text-muted-foreground">{source.video_id} / {source.ingest_status}</div>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground md:grid-cols-4">
                        <div>quality: {qualityScore ?? '-'}</div>
                        <div>naturalize: {naturalizationLabel}</div>
                        <div>extracted edges: {extractionCount}</div>
                        <div>empty hint: {emptyReason ?? '-'}</div>
                      </div>
                      {payload?.error && (
                        <div className="mt-2 rounded bg-destructive/10 px-2 py-1 text-xs text-destructive">
                          extraction error: {payload.error}
                        </div>
                      )}
                      {source.ingest_status === 'extracted' && extractionCount === 0 && (
                        <div className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
                          empty extraction candidate
                        </div>
                      )}
                      {transcriptPreview && (
                        <div className="mt-2 line-clamp-3 rounded bg-muted px-2 py-1 text-xs text-muted-foreground">
                          {transcriptPreview}
                        </div>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setExpandedSourceId((prev) => prev === source.id ? null : source.id)}
                    >
                      {isExpanded ? '詳細を閉じる' : '詳細を見る'}
                    </Button>
                  </div>
                  {isExpanded && <SourceDetail source={source} />}
                </div>
              )
            })}
          </CardContent>
        </Card>
      </div>

      <div className="mb-4 flex gap-2">
        {(['pending', 'approved', 'rejected'] as ReviewStatus[]).map((candidate) => (
          <Button
            key={candidate}
            variant={status === candidate ? 'default' : 'outline'}
            onClick={() => setStatus(candidate)}
          >
            {candidate}
          </Button>
        ))}
      </div>

      <div className="mb-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {(['all', 'strength', 'bouldering'] as const).map((goalType) => (
            <Button
              key={goalType}
              variant={graphGoalType === goalType ? 'default' : 'outline'}
              onClick={() => setGraphGoalType(goalType)}
            >
              {goalType}
            </Button>
          ))}
        </div>
        {graph ? <AdminTrainingProgressionGraph data={graph} /> : (
          <div className="rounded-md border p-6 text-sm text-muted-foreground">graph の取得に失敗しました</div>
        )}
      </div>

      {loading ? (
        <div className="rounded-md border p-6 text-sm text-muted-foreground">読み込み中...</div>
      ) : items.length === 0 ? (
        <div className="rounded-md border p-6 text-sm text-muted-foreground">対象データはありません</div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const form = forms[item.edge.id]
            return (
              <Card key={item.edge.id}>
                <CardHeader>
                  <CardTitle className="text-base">
                    {item.edge.from_label_raw} {item.edge.from_reps} {'->'} {item.edge.to_label_raw} {item.edge.to_reps}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-sm text-muted-foreground">
                    <div>{item.source.video_title}</div>
                    <div>{item.source.video_id} / {item.edge.review_status}</div>
                  </div>

                  {item.preset_review && (
                    <div className="rounded-md bg-blue-50 p-3 text-sm text-blue-700">
                      curated preset あり
                      <Button
                        variant="outline"
                        size="sm"
                        className="ml-3"
                        onClick={() => fillPreset(item)}
                      >
                        プリセット入力
                      </Button>
                    </div>
                  )}

                  {form && (
                    <div className="grid gap-3 md:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-medium">from_exercise_id</label>
                        <input
                          list="training-catalog-options"
                          className="w-full rounded-md border px-3 py-2 text-sm"
                          value={form.from_exercise_id}
                          onChange={(e) => updateForm(item.edge.id, { from_exercise_id: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium">to_exercise_id</label>
                        <input
                          list="training-catalog-options"
                          className="w-full rounded-md border px-3 py-2 text-sm"
                          value={form.to_exercise_id}
                          onChange={(e) => updateForm(item.edge.id, { to_exercise_id: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium">from_reps</label>
                        <input
                          type="number"
                          className="w-full rounded-md border px-3 py-2 text-sm"
                          value={form.from_reps}
                          onChange={(e) => updateForm(item.edge.id, { from_reps: parseInt(e.target.value, 10) || 1 })}
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium">to_reps</label>
                        <input
                          type="number"
                          className="w-full rounded-md border px-3 py-2 text-sm"
                          value={form.to_reps}
                          onChange={(e) => updateForm(item.edge.id, { to_reps: parseInt(e.target.value, 10) || 1 })}
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium">goal_scope (comma separated)</label>
                        <input
                          className="w-full rounded-md border px-3 py-2 text-sm"
                          value={form.goal_scope}
                          onChange={(e) => updateForm(item.edge.id, { goal_scope: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium">add_aliases (comma separated)</label>
                        <input
                          className="w-full rounded-md border px-3 py-2 text-sm"
                          value={form.add_aliases}
                          onChange={(e) => updateForm(item.edge.id, { add_aliases: e.target.value })}
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="mb-1 block text-sm font-medium">review_note</label>
                        <textarea
                          className="min-h-20 w-full rounded-md border px-3 py-2 text-sm"
                          value={form.review_note}
                          onChange={(e) => updateForm(item.edge.id, { review_note: e.target.value })}
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <Button
                      onClick={() => submitReview(item, 'approved')}
                      disabled={savingEdgeId === item.edge.id}
                    >
                      {savingEdgeId === item.edge.id ? '保存中...' : 'Approve'}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => submitReview(item, 'rejected')}
                      disabled={savingEdgeId === item.edge.id}
                    >
                      Reject
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => jumpToSource(item.source.id)}
                    >
                      source を表示
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
      <datalist id="training-catalog-options">
        {catalog.map((exercise) => (
          <option key={exercise.id} value={exercise.id}>
            {exercise.name_ja}
          </option>
        ))}
      </datalist>
    </div>
  )
}
