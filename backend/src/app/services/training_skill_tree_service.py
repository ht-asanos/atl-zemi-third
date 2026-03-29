from __future__ import annotations

from collections import defaultdict, deque
from datetime import date, timedelta
from uuid import UUID

from app.repositories import feedback_event_repo, log_repo, training_progression_repo
from app.schemas.feedback import FeedbackEventDetailResponse
from app.schemas.log import WorkoutLogResponse
from app.schemas.training_progression import (
    AdminTrainingProgressionGraphEdge,
    AdminTrainingProgressionGraphNode,
    AdminTrainingProgressionGraphResponse,
    AdminTrainingProgressionGraphSummary,
    AdminTrainingProgressionGraphTrack,
    AdminTrainingProgressionUnmappedEdge,
    TrainingProgressionEdgeResponse,
    TrainingProgressionReviewItem,
    TrainingSkillTreeEdge,
    TrainingSkillTreeNode,
    TrainingSkillTreeResponse,
    TrainingSkillTreeSummary,
    TrainingSkillTreeTrack,
)
from app.services.training_catalog import get_exercise_definition, normalize_available_equipment
from app.services.training_progression_planner import (
    _best_completed_reps,
    _negative_feedback_exercise_ids,
    recommend_progression_replacements,
)

from supabase import AsyncClient


def _latest_logs_by_exercise(logs: list[WorkoutLogResponse]) -> dict[str, WorkoutLogResponse]:
    latest: dict[str, WorkoutLogResponse] = {}
    for log in logs:
        prev = latest.get(log.exercise_id)
        if prev is None or (log.log_date, log.created_at) > (prev.log_date, prev.created_at):
            latest[log.exercise_id] = log
    return latest


def _latest_feedback_by_exercise(events: list[FeedbackEventDetailResponse]) -> dict[str, FeedbackEventDetailResponse]:
    latest: dict[str, FeedbackEventDetailResponse] = {}
    for event in events:
        if not event.exercise_id:
            continue
        prev = latest.get(event.exercise_id)
        if prev is None or event.created_at > prev.created_at:
            latest[event.exercise_id] = event
    return latest


def _group_edges_into_tracks(
    edges: list[TrainingProgressionEdgeResponse],
) -> list[tuple[str, list[str], list[TrainingProgressionEdgeResponse]]]:
    adjacency: dict[str, list[TrainingProgressionEdgeResponse]] = defaultdict(list)
    reverse_adjacency: dict[str, list[TrainingProgressionEdgeResponse]] = defaultdict(list)
    node_ids: set[str] = set()
    incoming_ids: set[str] = set()

    for edge in edges:
        if not edge.from_exercise_id or not edge.to_exercise_id:
            continue
        adjacency[edge.from_exercise_id].append(edge)
        reverse_adjacency[edge.to_exercise_id].append(edge)
        node_ids.add(edge.from_exercise_id)
        node_ids.add(edge.to_exercise_id)
        incoming_ids.add(edge.to_exercise_id)

    if not node_ids:
        return []

    roots = sorted(node_ids - incoming_ids) or sorted(node_ids)
    visited_nodes: set[str] = set()
    tracks: list[tuple[str, list[str], list[TrainingProgressionEdgeResponse]]] = []

    for root in roots:
        if root in visited_nodes:
            continue
        queue = deque([root])
        component_nodes: set[str] = set()
        component_edges: list[TrainingProgressionEdgeResponse] = []
        seen_edge_ids: set[str] = set()
        ordered_nodes: list[str] = []

        while queue:
            node_id = queue.popleft()
            if node_id in component_nodes:
                continue
            component_nodes.add(node_id)
            ordered_nodes.append(node_id)

            outgoing = sorted(
                adjacency.get(node_id, []),
                key=lambda edge: (edge.from_reps, edge.to_reps, edge.to_exercise_id or ""),
            )
            for edge in outgoing:
                edge_id = str(edge.id)
                if edge_id not in seen_edge_ids:
                    component_edges.append(edge)
                    seen_edge_ids.add(edge_id)
                if edge.to_exercise_id:
                    queue.append(edge.to_exercise_id)

            for edge in reverse_adjacency.get(node_id, []):
                if edge.from_exercise_id and edge.from_exercise_id not in component_nodes:
                    queue.append(edge.from_exercise_id)

        visited_nodes.update(component_nodes)
        tracks.append((root, ordered_nodes, component_edges))

    return tracks


def _find_current_node_id(node_order: list[str], best_reps: dict[str, int]) -> str | None:
    current_node_id: str | None = None
    for node_id in node_order:
        if best_reps.get(node_id, 0) > 0:
            current_node_id = node_id
    return current_node_id


def _node_status(
    *,
    node_id: str,
    current_node_id: str | None,
    best_reps: dict[str, int],
    next_thresholds: dict[str, int],
    recommended_targets: dict[str, str],
    negative_ids: set[str],
) -> str:
    if node_id in recommended_targets:
        return "recommended"
    if node_id in negative_ids:
        return "blocked"
    if current_node_id == node_id:
        return "current"

    best = best_reps.get(node_id, 0)
    next_threshold = next_thresholds.get(node_id)
    if best > 0 and (next_threshold is None or best >= next_threshold):
        return "mastered"
    if best > 0:
        return "unlocked"
    return "locked"


def _goal_matches(goal_scope: list[str], goal_type: str) -> bool:
    return goal_type == "all" or not goal_scope or goal_type in goal_scope


async def build_training_skill_tree(
    supabase: AsyncClient,
    *,
    user_id: UUID,
    goal_type: str,
    start_date: date,
    available_equipment: list[str] | set[str] | None = None,
) -> TrainingSkillTreeResponse:
    equipment = normalize_available_equipment(available_equipment)
    begin_date = start_date - timedelta(days=14)
    logs = await log_repo.get_workout_logs_in_range(supabase, user_id, begin_date, start_date)
    feedback_events = await feedback_event_repo.get_feedback_events_in_range(
        supabase,
        user_id=user_id,
        start_date=begin_date,
        end_date=start_date + timedelta(days=1),
        domain="workout",
    )
    approved_edges = await training_progression_repo.list_approved_edges(supabase, goal_type=goal_type)
    best_reps = _best_completed_reps(logs)
    negative_ids = _negative_feedback_exercise_ids(feedback_events)
    latest_logs = _latest_logs_by_exercise(logs)
    latest_feedback = _latest_feedback_by_exercise(feedback_events)
    recommendations = await recommend_progression_replacements(
        supabase,
        user_id=user_id,
        start_date=start_date,
        goal_type=goal_type,
        available_equipment=sorted(equipment),
    )
    recommended_targets = {rec.replacement_id: rec.reason for rec in recommendations.values() if rec.replacement_id}

    tracks: list[TrainingSkillTreeTrack] = []
    for root_id, ordered_node_ids, track_edges in _group_edges_into_tracks(approved_edges):
        next_thresholds = {edge.from_exercise_id: edge.from_reps for edge in track_edges if edge.from_exercise_id}
        current_node_id = _find_current_node_id(ordered_node_ids, best_reps)
        nodes: list[TrainingSkillTreeNode] = []
        for node_id in ordered_node_ids:
            exercise = get_exercise_definition(node_id)
            if exercise is None:
                continue
            nodes.append(
                TrainingSkillTreeNode(
                    exercise_id=node_id,
                    name_ja=exercise.name_ja,
                    required_equipment=exercise.required_equipment,
                    best_completed_reps=best_reps.get(node_id, 0),
                    status=_node_status(
                        node_id=node_id,
                        current_node_id=current_node_id,
                        best_reps=best_reps,
                        next_thresholds=next_thresholds,
                        recommended_targets=recommended_targets,
                        negative_ids=negative_ids,
                    ),
                    next_threshold_reps=next_thresholds.get(node_id),
                    recommendation_reason=recommended_targets.get(node_id),
                    latest_log_summary=(
                        {
                            "log_date": latest_logs[node_id].log_date.isoformat(),
                            "sets": latest_logs[node_id].sets,
                            "reps": latest_logs[node_id].reps,
                            "rpe": latest_logs[node_id].rpe,
                            "completed": latest_logs[node_id].completed,
                        }
                        if node_id in latest_logs
                        else None
                    ),
                    latest_feedback_summary=(
                        {
                            "created_at": latest_feedback[node_id].created_at.isoformat(),
                            "source_text": latest_feedback[node_id].source_text,
                            "tags": [tag.tag for tag in latest_feedback[node_id].tags],
                        }
                        if node_id in latest_feedback
                        else None
                    ),
                )
            )

        if not nodes:
            continue

        edges = [
            TrainingSkillTreeEdge(
                from_exercise_id=edge.from_exercise_id,
                to_exercise_id=edge.to_exercise_id,
                from_reps_required=edge.from_reps,
                to_reps_target=edge.to_reps,
                is_recommended_path=edge.to_exercise_id in recommended_targets,
            )
            for edge in track_edges
            if edge.from_exercise_id and edge.to_exercise_id
        ]
        title = nodes[0].name_ja
        tracks.append(
            TrainingSkillTreeTrack(
                track_id=root_id,
                title=title,
                nodes=nodes,
                edges=edges,
            )
        )

    summary = TrainingSkillTreeSummary(
        goal_type=goal_type,
        available_edge_count=len(approved_edges),
        recommended_count=len(recommended_targets),
        has_negative_feedback=bool(negative_ids),
    )
    return TrainingSkillTreeResponse(summary=summary, tracks=tracks)


def _group_review_items_into_tracks(
    items: list[TrainingProgressionReviewItem],
) -> tuple[list[AdminTrainingProgressionGraphTrack], list[AdminTrainingProgressionUnmappedEdge]]:
    mapped_items: list[TrainingProgressionReviewItem] = []
    unmapped_edges: list[AdminTrainingProgressionUnmappedEdge] = []
    for item in items:
        if item.edge.from_exercise_id and item.edge.to_exercise_id:
            mapped_items.append(item)
            continue
        unmapped_edges.append(
            AdminTrainingProgressionUnmappedEdge(
                edge_id=item.edge.id,
                from_label_raw=item.edge.from_label_raw,
                to_label_raw=item.edge.to_label_raw,
                from_reps=item.edge.from_reps,
                to_reps=item.edge.to_reps,
                review_status=item.edge.review_status,
                video_id=item.source.video_id,
                video_title=item.source.video_title,
            )
        )

    if not mapped_items:
        return [], unmapped_edges

    edge_like = [
        TrainingProgressionEdgeResponse(
            id=item.edge.id,
            source_id=item.edge.source_id,
            from_label_raw=item.edge.from_label_raw,
            from_exercise_id=item.edge.from_exercise_id,
            from_reps=item.edge.from_reps,
            to_label_raw=item.edge.to_label_raw,
            to_exercise_id=item.edge.to_exercise_id,
            to_reps=item.edge.to_reps,
            relation_type=item.edge.relation_type,
            goal_scope=item.edge.goal_scope,
            evidence_text=item.edge.evidence_text,
            confidence=item.edge.confidence,
            review_status=item.edge.review_status,
            review_note=item.edge.review_note,
            reviewed_by=item.edge.reviewed_by,
            reviewed_at=item.edge.reviewed_at,
            created_at=item.edge.created_at,
        )
        for item in mapped_items
    ]
    grouped = _group_edges_into_tracks(edge_like)
    item_by_edge_id = {str(item.edge.id): item for item in mapped_items}
    tracks: list[AdminTrainingProgressionGraphTrack] = []
    for root_id, ordered_node_ids, track_edges in grouped:
        review_counts: dict[str, int] = defaultdict(int)
        for edge in track_edges:
            if edge.from_exercise_id:
                review_counts[edge.from_exercise_id] += 1
            if edge.to_exercise_id:
                review_counts[edge.to_exercise_id] += 1

        nodes: list[AdminTrainingProgressionGraphNode] = []
        for node_id in ordered_node_ids:
            exercise = get_exercise_definition(node_id)
            if exercise is None:
                continue
            nodes.append(
                AdminTrainingProgressionGraphNode(
                    exercise_id=node_id,
                    name_ja=exercise.name_ja,
                    required_equipment=exercise.required_equipment,
                    review_count=review_counts.get(node_id, 0),
                )
            )
        if not nodes:
            continue

        edges: list[AdminTrainingProgressionGraphEdge] = []
        for edge in track_edges:
            item = item_by_edge_id.get(str(edge.id))
            if item is None or not edge.from_exercise_id or not edge.to_exercise_id:
                continue
            edges.append(
                AdminTrainingProgressionGraphEdge(
                    edge_id=edge.id,
                    from_exercise_id=edge.from_exercise_id,
                    to_exercise_id=edge.to_exercise_id,
                    from_reps_required=edge.from_reps,
                    to_reps_target=edge.to_reps,
                    review_status=edge.review_status,
                    video_id=item.source.video_id,
                    video_title=item.source.video_title,
                    review_note=edge.review_note,
                )
            )
        tracks.append(
            AdminTrainingProgressionGraphTrack(
                track_id=root_id,
                title=nodes[0].name_ja,
                nodes=nodes,
                edges=edges,
            )
        )
    return tracks, unmapped_edges


async def build_admin_training_progression_graph(
    supabase: AsyncClient,
    *,
    review_status: str,
    goal_type: str = "all",
    limit: int = 200,
) -> AdminTrainingProgressionGraphResponse:
    items = await training_progression_repo.list_review_items(
        supabase,
        review_status=review_status,
        limit=limit,
    )
    filtered_items = [item for item in items if _goal_matches(item.edge.goal_scope, goal_type)]
    tracks, unmapped_edges = _group_review_items_into_tracks(filtered_items)
    return AdminTrainingProgressionGraphResponse(
        summary=AdminTrainingProgressionGraphSummary(
            status=review_status,
            goal_type=goal_type,
            edge_count=len(filtered_items),
            track_count=len(tracks),
            unmapped_edge_count=len(unmapped_edges),
        ),
        tracks=tracks,
        unmapped_edges=unmapped_edges,
    )
