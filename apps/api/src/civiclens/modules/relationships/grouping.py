"""Turn a list of fresh reports into groups an officer can act on.

:mod:`civiclens.modules.relationships.evaluator` answers one question about two
reports. This answers the question a ward officer actually has in front of them at
nine in the morning: *of the forty things reported overnight, how many problems are
there?* Forty reports of one flooded junction is one problem and one crew. Reading
it as forty is how a backlog becomes unmanageable, and reading two potholes as one
is how a crew fills one hole and drives past the other.

**The order is geometry first, then intent.** Location and category and time are
cheap, deterministic and checkable, so they narrow forty reports to a handful of
candidates. Only then does the question "are these two people describing the same
thing?" get asked -- and it is a question about language, which is what the
``intent_check`` argument is for. Nothing here reads an image or infers meaning from
text on its own.

Three rules this module will not bend:

*Clustering is against the group's lead, never transitively.* If A matches B and B
matches C, that does not put A and C together -- A is compared to the lead directly
or it starts its own group. Chaining is how a 1.5 km gate quietly becomes a
five-kilometre group covering half a ward, and nobody notices because the output is
still just a number.

*Uncertainty separates, and never merges.* ``grouping-v1`` says so
(``uncertainty_favors_separation``). Where the evidence runs out, the answer is
"these are proposed as related, an officer decides", never "these are the same".

*Safety never groups with non-safety.* A live wire reported alongside a pothole must
not end up counted inside the pothole's group, where its own lane would never see
it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from civiclens.bootstrap.policy import load_policy_bundle
from civiclens.domain.photo_integrity import hamming_distance
from civiclens.modules.relationships.evaluator import ReportFeatures, evaluate_same_incident

# Out of 64 bits. Two photographs of one pothole taken minutes apart from slightly
# different angles land well inside this; two different subjects at the same
# junction land outside it. Used in one direction only -- close hashes corroborate a
# grouping that geometry already proposed, and distant hashes never break one, because
# a difference hash is easily moved by nothing more than the light changing.
MAX_PHOTO_HASH_DISTANCE = 12

IntentVerdict = Literal["agree", "disagree", "abstain"]
JoinReason = Literal["lead", "photo_corroborated", "intent_agreed", "geometry_only"]
ConfidenceBand = Literal["high", "review", "not_eligible"]


@dataclass(frozen=True)
class GroupingCandidate:
    """One report, reduced to what grouping is allowed to look at.

    Deliberately not the intake record. Grouping has no business reading the report
    text, the reporter's receipt, or anything else on that object, and a narrow input
    is how that stays true rather than being a note in a document.
    """

    features: ReportFeatures
    # Partitions before anything else runs. See the module docstring.
    safety_signalled: bool = False
    # The difference hash of the attached photo, if there is one. Content-derived and
    # carries nothing about where the photo was taken -- that was stripped before
    # storage. See `domain.photo_integrity`.
    photo_hash: str | None = None


@dataclass(frozen=True)
class GroupMember:
    report_id: UUID
    joined_by: JoinReason
    # The pairwise evidence from the gate, unedited, so an officer disputing a
    # grouping can be shown the actual numbers rather than a summary of them.
    evidence: dict[str, str | float | bool | None]


@dataclass(frozen=True)
class ReportGroup:
    """Reports proposed as one problem. A proposal, never a decision."""

    # The earliest report in the group. It is the lead because every other member was
    # compared against it, and because the statutory clock runs from the first time
    # anybody reported the problem -- not from the newest duplicate, which would let a
    # deadline be reset by a fresh complaint.
    lead_report_id: UUID
    category: str
    first_reported_at: datetime
    members: tuple[GroupMember, ...]
    # ``None`` for a group of one, because no relationship is being claimed and any
    # band would be answering a question nobody asked. Officers read this as
    # "confidence that these reports are the same problem", and a lone report has no
    # such statement to make.
    confidence_band: ConfidenceBand | None
    safety_signalled: bool
    explanation: str

    @property
    def report_count(self) -> int:
        return len(self.members)

    @property
    def is_grouped(self) -> bool:
        return len(self.members) > 1


def group_reports(
    candidates: Sequence[GroupingCandidate],
    *,
    intent_check: Callable[[UUID, UUID], IntentVerdict] | None = None,
) -> list[ReportGroup]:
    """Group reports into suspected single problems, oldest report leading each group.

    ``intent_check`` is asked, for a pair that geometry has already accepted, whether
    the two reports describe the same thing. It receives ``(lead_id, candidate_id)``
    and may answer ``disagree`` to split a pair geometry would have joined. Omitted,
    every pair is treated as ``abstain``: the grouping still happens, and it is
    reported at ``review`` confidence rather than ``high``, which is the correct
    answer when the question was never asked.

    The result is ordered newest-group-first, matching how the officer board reads.
    """
    verdict = intent_check or _abstain
    groups: list[_MutableGroup] = []

    # Oldest first, so the lead of every group is the first person who reported the
    # problem. Sorted rather than assumed, because `list_fresh()` returns newest-first
    # and a caller that forgot would silently get the newest report leading, and with
    # it the wrong `first_reported_at` and the wrong statutory deadline.
    for candidate in sorted(candidates, key=lambda item: item.features.event_at):
        for group in groups:
            if group.safety_signalled != candidate.safety_signalled:
                continue
            joined = _try_join(group, candidate, verdict)
            if joined is not None:
                group.members.append(joined)
                group.confidence_band = _weakest(group.confidence_band, _band_of(joined))
                break
        else:
            groups.append(_new_group(candidate))

    return sorted(
        (group.freeze() for group in groups),
        key=lambda group: group.first_reported_at,
        reverse=True,
    )


def _abstain(lead_report_id: UUID, other_report_id: UUID) -> IntentVerdict:
    """The answer when nothing was asked. Not a guess, and not an agreement."""
    del lead_report_id, other_report_id
    return "abstain"


@dataclass
class _MutableGroup:
    lead: GroupingCandidate
    members: list[GroupMember]
    confidence_band: ConfidenceBand | None
    safety_signalled: bool

    def freeze(self) -> ReportGroup:
        return ReportGroup(
            lead_report_id=self.lead.features.report_id,
            category=self.lead.features.category,
            first_reported_at=self.lead.features.event_at,
            members=tuple(self.members),
            confidence_band=self.confidence_band,
            safety_signalled=self.safety_signalled,
            explanation=_explain(self),
        )


def _new_group(candidate: GroupingCandidate) -> _MutableGroup:
    return _MutableGroup(
        lead=candidate,
        members=[
            GroupMember(
                report_id=candidate.features.report_id,
                joined_by="lead",
                evidence={"role": "first_report_in_group"},
            )
        ],
        # No band until a second report joins. A group of one makes no claim, and
        # seeding a band here would then cap every group at it: `_weakest` takes the
        # lowest, so a starting value of "review" would quietly discard the "high" a
        # photo-corroborated join had earned.
        confidence_band=None,
        safety_signalled=candidate.safety_signalled,
    )


def _try_join(
    group: _MutableGroup,
    candidate: GroupingCandidate,
    verdict: Callable[[UUID, UUID], IntentVerdict],
) -> GroupMember | None:
    """Decide whether ``candidate`` belongs with ``group``'s lead, and on what grounds."""
    decision = evaluate_same_incident(group.lead.features, candidate.features)
    if decision.relation_type != "same_incident":
        return None

    lead_id = group.lead.features.report_id
    other_id = candidate.features.report_id
    intent = verdict(lead_id, other_id)
    if intent == "disagree":
        # Geometry said "same place, same category, same week" and the reading of the
        # two descriptions says they are different problems. Two potholes on one road
        # are exactly this case, and geometry alone cannot tell them apart.
        return None

    evidence = dict(decision.feature_evidence)
    evidence["geometry_band"] = decision.confidence_band
    evidence["intent_verdict"] = intent

    photo_gap = _photo_gap(group.lead, candidate)
    evidence["photo_hash_distance"] = photo_gap
    if intent == "agree":
        return GroupMember(report_id=other_id, joined_by="intent_agreed", evidence=evidence)
    if photo_gap is not None and photo_gap <= MAX_PHOTO_HASH_DISTANCE:
        return GroupMember(report_id=other_id, joined_by="photo_corroborated", evidence=evidence)
    return GroupMember(report_id=other_id, joined_by="geometry_only", evidence=evidence)


def _photo_gap(left: GroupingCandidate, right: GroupingCandidate) -> int | None:
    """How far apart the two attached photos are, or None if there is no pair to compare.

    Tolerant of a malformed hash on purpose. It arrives from a database column, and a
    row written by an older version must degrade to "no photo evidence" rather than
    take down the officer's board.
    """
    if left.photo_hash is None or right.photo_hash is None:
        return None
    try:
        return hamming_distance(left.photo_hash, right.photo_hash)
    except ValueError:
        return None


def _band_of(member: GroupMember) -> ConfidenceBand:
    if member.joined_by in {"intent_agreed", "photo_corroborated"}:
        # Something beyond geometry agreed: either a reading of the two descriptions,
        # or two photographs of the same thing.
        geometry_band = member.evidence.get("geometry_band")
        return "high" if geometry_band == "high" else "review"
    # Geometry alone, with the intent question unanswered. `grouping-v1` says
    # uncertainty favours separation, so this cannot be reported as high confidence
    # no matter how good the coordinates were -- a 1.5 km gate admits two genuinely
    # different problems on one street, and only the unanswered question separates them.
    return "review"


def _weakest(current: ConfidenceBand | None, incoming: ConfidenceBand) -> ConfidenceBand:
    """A group is only as certain as its least certain link."""
    if current is None:
        return incoming
    order: tuple[ConfidenceBand, ...] = ("not_eligible", "review", "high")
    return current if order.index(current) <= order.index(incoming) else incoming


def _explain(group: _MutableGroup) -> str:
    """One sentence an officer can check against the evidence, not a confidence score."""
    policy = load_policy_bundle().grouping.same_incident
    if len(group.members) == 1:
        return (
            "One report. A single report is not yet evidence of a recurring problem, and "
            "nothing has been grouped with it."
        )
    joined = {member.joined_by for member in group.members} - {"lead"}
    grounds = (
        f"same category, within {policy.max_hours} hours and "
        f"{policy.max_distance_km:g} km of the first report"
    )
    if "photo_corroborated" in joined:
        grounds += ", and the attached photos match"
    if "intent_agreed" in joined:
        grounds += ", and the descriptions were read as the same problem"
    return (
        f"{len(group.members)} reports proposed as one problem: {grounds}. "
        "Proposed only — an officer confirms or separates them."
    )
