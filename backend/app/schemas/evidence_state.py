from typing import Literal

from pydantic import BaseModel

EvidenceStrength = Literal["none", "low", "medium", "high", "conflicting"]
EvidenceAnswerStatus = Literal[
    "answered",
    "partially_answered",
    "refused_no_evidence",
    "refused_ambiguous_material",
    "needs_more_material",
]


class EvidenceStateResponse(BaseModel):
    evidence_strength: EvidenceStrength
    source_coverage: float
    supported_claim_count: int
    unsupported_claim_count: int
    contradicted_claim_count: int
    answer_status: EvidenceAnswerStatus
