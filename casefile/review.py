"""Human review actions with atomic case-state and audit updates."""
from __future__ import annotations

import json

from contracts.models import Case, ReviewerAction
from casefile.audit import write
from db import store


_STATUS = {"CONFIRM": "SAR_FILED", "DISMISS": "DISMISSED", "ESCALATE": "ESCALATED",
           "REQUEST_INFO": "IN_REVIEW"}


def review(case_id: str, action: ReviewerAction) -> Case:
    """Apply a human decision and append its immutable audit evidence atomically."""
    with store.connect() as conn:
        row = conn.execute("SELECT data FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(f"case not found: {case_id}")
        case = Case(**json.loads(row["data"]))
        if action.action == "CONFIRM" and case.sar is None:
            raise ValueError("cannot file a case without a drafted SAR")
        before = {"status": case.status, "tier": case.tier, "score": case.current_score}
        case.status = _STATUS[action.action]
        case.reviewer_actions.append(action)
        if action.action == "CONFIRM" and case.sar:
            case.sar.status = "APPROVED"
        after = {"status": case.status, "tier": case.tier, "score": case.current_score}
        audit = write(f"user:{action.reviewer}", action.action, "Case", case_id, action.note,
                      before=before, after=after, at=action.at)
        feedback = []
        if action.action == "DISMISS":
            feedback = [
                write("agent:review", "SUPPRESSION_RULE_ADDED", "Case", case_id,
                      "Customer × watchlist-entry suppression rule recorded.", at=action.at),
                write("agent:review", "NEGATIVE_EXAMPLE_RECORDED", "Case", case_id,
                      "Dismissal recorded as a negative example for ER threshold tuning.", at=action.at),
            ]
        data = case.model_dump(mode="json")
        with conn:
            conn.execute("UPDATE cases SET status=?, tier=?, data=? WHERE case_id=?",
                         (case.status, case.tier, json.dumps(data), case_id))
            if case.sar:
                conn.execute("UPDATE sars SET status=?, data=? WHERE sar_id=?",
                             (case.sar.status, case.sar.model_dump_json(), case.sar.sar_id))
            for event in [audit, *feedback]:
                item = event.model_dump(mode="json")
                conn.execute("INSERT INTO audit_events "
                             "(audit_id,at,actor,action,object_type,object_id,before,after,rationale) "
                             "VALUES (?,?,?,?,?,?,?,?,?)",
                             (item["audit_id"], item["at"], item["actor"], item["action"],
                              item["object_type"], item["object_id"],
                              json.dumps(item["before"]) if item["before"] else None,
                              json.dumps(item["after"]) if item["after"] else None,
                              item["rationale"]))
    return case
