from __future__ import annotations

from collections import defaultdict

from app.models import Segment


def build_835_summary(segments: list[Segment]) -> list[dict[str, str | float]]:
    rows: list[dict[str, str | float]] = []
    current_adj: list[str] = []
    eft_ref = ""

    for seg in segments:
        if seg.id == "TRN" and len(seg.elements) > 1:
            eft_ref = seg.elements[1]

        if seg.id == "CAS" and len(seg.elements) > 1:
            reason = seg.elements[1]
            amount = seg.elements[2] if len(seg.elements) > 2 else "0"
            current_adj.append(f"{reason}:{amount}")

        if seg.id == "CLP" and len(seg.elements) > 4:
            row = {
                "claim_id": seg.elements[0],
                "status_code": seg.elements[1],
                "billed": _to_float(seg.elements[2]),
                "paid": _to_float(seg.elements[3]),
                "patient_responsibility": _to_float(seg.elements[4]),
                "adjustments": ", ".join(current_adj),
                "eft_or_check_ref": eft_ref,
            }
            rows.append(row)
            current_adj = []

    return rows


def build_834_summary(segments: list[Segment]) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for seg in segments:
        if seg.id == "INS":
            if current:
                members.append(current)
            current = {
                "maintenance_type": seg.elements[2] if len(seg.elements) > 2 else "",
                "relationship": seg.elements[1] if len(seg.elements) > 1 else "",
                "member_id": "",
                "last_name": "",
                "first_name": "",
                "coverage_start": "",
                "coverage_end": "",
            }
        elif seg.id == "REF" and current and len(seg.elements) > 1 and seg.elements[0] in {"0F", "1L"}:
            current["member_id"] = seg.elements[1]
        elif seg.id == "NM1" and current and len(seg.elements) > 3:
            current["last_name"] = seg.elements[2]
            current["first_name"] = seg.elements[3]
        elif seg.id == "DTP" and current and len(seg.elements) > 2:
            if seg.elements[0] == "348":
                current["coverage_start"] = seg.elements[2]
            if seg.elements[0] == "349":
                current["coverage_end"] = seg.elements[2]

    if current:
        members.append(current)

    return members


def build_family_grouping(members: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for member in members:
        key = member.get("member_id", "UNKNOWN")[:9]
        grouped[key].append(member)

    return [{"family_key": k, "members": v, "count": len(v)} for k, v in grouped.items()]


def _to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0

