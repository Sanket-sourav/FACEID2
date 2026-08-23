"""
Turns raw per-frame recognition observations into attendance decisions.

Core principle (master plan): no student is auto-marked present or absent
without sufficient evidence. Every enrolled student ends up in one of:
  PRESENT              - high confidence, auto-accepted
  PRESENT_REVIEW        - medium confidence, present but flagged for review
  NEEDS_REVIEW          - conflicting/ambiguous evidence
  NOT_OBSERVED          - no reliable evidence either way (NOT "absent")
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src import config
from src.services.face_recognizer import Candidate


@dataclass
class Observation:
    frame_index: int
    timestamp_sec: float
    best: Candidate
    second: Optional[Candidate]
    quality: float

    @property
    def margin(self) -> float:
        if self.second is None:
            return self.best.similarity
        return self.best.similarity - self.second.similarity


@dataclass
class StudentEvidence:
    student_id: str
    student_name: str
    observations: List[Observation] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.observations)

    @property
    def avg_similarity(self) -> float:
        if not self.observations:
            return 0.0
        return sum(o.best.similarity for o in self.observations) / len(self.observations)

    @property
    def avg_margin(self) -> float:
        if not self.observations:
            return 0.0
        return sum(o.margin for o in self.observations) / len(self.observations)


@dataclass
class AttendanceDecision:
    student_id: str
    student_name: str
    status: str            # PRESENT | PRESENT_REVIEW | NEEDS_REVIEW | NOT_OBSERVED
    confidence: float
    evidence_count: int
    avg_similarity: float
    avg_margin: float
    requires_review: bool
    reason: str


def build_observations(
    frame_index: int,
    timestamp_sec: float,
    candidates: List[Candidate],
    quality: float,
) -> Optional[Observation]:
    """Given ranked candidates for one detected+quality-passed face, decide
    whether this observation counts as evidence for anyone at all."""
    if not candidates:
        return None
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None

    if best.similarity < config.MATCH_THRESHOLD:
        return None  # doesn't look like anyone on the roster

    return Observation(frame_index=frame_index, timestamp_sec=timestamp_sec, best=best, second=second, quality=quality)


def aggregate(observations: List[Observation]) -> Dict[str, StudentEvidence]:
    """Groups observations by the *best*-matched student id."""
    grouped: Dict[str, StudentEvidence] = {}
    for obs in observations:
        sid = obs.best.student_id
        if sid not in grouped:
            grouped[sid] = StudentEvidence(student_id=sid, student_name=obs.best.student_name)
        grouped[sid].observations.append(obs)
    return grouped


def decide_student(evidence: Optional[StudentEvidence], student_id: str, student_name: str) -> AttendanceDecision:
    if evidence is None or evidence.count == 0:
        return AttendanceDecision(
            student_id=student_id,
            student_name=student_name,
            status="NOT_OBSERVED",
            confidence=0.0,
            evidence_count=0,
            avg_similarity=0.0,
            avg_margin=0.0,
            requires_review=True,
            reason="No face observations matched this student above the match threshold.",
        )

    n = evidence.count
    avg_sim = evidence.avg_similarity
    avg_margin = evidence.avg_margin
    low_margin_count = sum(1 for o in evidence.observations if o.margin < config.MARGIN_THRESHOLD)
    consistency = 1.0 - (low_margin_count / n)

    if (
        n >= config.HIGH_CONFIDENCE_MIN_OBSERVATIONS
        and avg_sim >= config.HIGH_CONFIDENCE_MIN_AVG_SIMILARITY
        and consistency >= config.MIN_CONSISTENCY_RATIO
    ):
        return AttendanceDecision(
            student_id=student_id,
            student_name=student_name,
            status="PRESENT",
            confidence=min(0.99, avg_sim + 0.1 * consistency),
            evidence_count=n,
            avg_similarity=avg_sim,
            avg_margin=avg_margin,
            requires_review=False,
            reason=f"{n} consistent high-quality observations, avg similarity {avg_sim:.2f}.",
        )

    if (
        n >= config.MEDIUM_CONFIDENCE_MIN_OBSERVATIONS
        and avg_sim >= config.MEDIUM_CONFIDENCE_MIN_AVG_SIMILARITY
        and consistency >= config.MEDIUM_MIN_CONSISTENCY_RATIO
    ):
        return AttendanceDecision(
            student_id=student_id,
            student_name=student_name,
            status="PRESENT_REVIEW",
            confidence=avg_sim,
            evidence_count=n,
            avg_similarity=avg_sim,
            avg_margin=avg_margin,
            requires_review=True,
            reason=f"Only {n} observations or borderline similarity ({avg_sim:.2f}) — verify before finalizing.",
        )

    return AttendanceDecision(
        student_id=student_id,
        student_name=student_name,
        status="NEEDS_REVIEW",
        confidence=avg_sim,
        evidence_count=n,
        avg_similarity=avg_sim,
        avg_margin=avg_margin,
        requires_review=True,
        reason="Weak or inconsistent evidence; best-vs-second-best margin too small.",
    )


def decide_all(
    observations: List[Observation],
    roster: Dict[str, str],  # student_id -> student_name
) -> List[AttendanceDecision]:
    grouped = aggregate(observations)
    decisions = []
    for student_id, student_name in roster.items():
        decisions.append(decide_student(grouped.get(student_id), student_id, student_name))
    decisions.sort(key=lambda d: (-d.confidence, d.student_name))
    return decisions
