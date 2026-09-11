"""Appendix A criteria as independently testable, explainable components.

Only criteria whose method is implemented are exported. No function in this
package issues an overall duplication verdict.
"""
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.rules.model import (
    CriterionOutcome, CriterionResult, CriterionValue, EvidenceSide, MethodApproval,
)

__all__ = [
    "CriterionOutcome", "CriterionResult", "CriterionValue", "EvidenceSide", "MethodApproval",
    "evaluate_angular_resolution",
]
