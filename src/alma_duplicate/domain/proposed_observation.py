"""Source-independent proposed observations; construct through the validator.

Frozen values describe supplied evidence, not confirmed observing feasibility or
duplication. Missing scientific information is represented by None/UNKNOWN.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


CONTINUUM_SETUP_DECLARATION = "AT_LEAST_TWO_USABLE_WINDOWS_GT_1_8_GHZ"

# Explicit wire contract. The successor is reserved, not executable in step 02.
LINE_SCOPE_LEGACY = "LEGACY_SETUP_ENUMERATION_V1"
LINE_SCOPE_SUBMITTED = "SUBMITTED_LINE_REQUIREMENTS_V2"


class SearchReadiness(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class RequestIssue:
    category: str  # ERROR, MISSING, CAPABILITY, EVIDENCE
    code: str
    path: str
    message: str
    rule_id: str | None = None
    side: str = "PROPOSED"


@dataclass(frozen=True, slots=True)
class RequestQuantity:
    value: float
    unit: str
    raw_value: object
    raw_unit: str
    conversion_version: str = "1"


@dataclass(frozen=True, slots=True)
class RequestFrequency:
    quantity: RequestQuantity
    kind: str
    frame: str
    origin: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class RequestPosition:
    ra_deg: float
    dec_deg: float
    frame: str = "ICRS"
    conversion_version: str = "1"


@dataclass(frozen=True, slots=True)
class RequestInterval:
    lower_ghz: float
    upper_ghz: float
    midpoint_ghz: float
    span_ghz: float
    kind: str
    origin: str
    scientifically_validated: bool = False


@dataclass(frozen=True, slots=True)
class ProposedWindow:
    window_id: str
    representation: str
    center: RequestFrequency | None
    bandwidth: RequestQuantity | None
    bandwidth_kind: str
    lower: RequestFrequency | None
    upper: RequestFrequency | None
    interval: RequestInterval | None
    correlator_mode: str
    mode_origin: Mapping[str, object]
    channel_spacing: RequestQuantity | None
    spectral_resolution: RequestQuantity | None


@dataclass(frozen=True, slots=True)
class ProposedSensitivity:
    sensitivity_id: str
    purpose: str
    scope: str
    setup_id: str | None
    window_ids: tuple[str, ...]
    rms: RequestQuantity | None
    basis: str
    aggregate_path: str | None
    reference_frequency: RequestFrequency | None
    bandwidth_used_for_sensitivity: RequestQuantity | None
    bandwidth_meaning: str
    bandwidth_origin: Mapping[str, object]
    target_aggregate_bandwidth: RequestQuantity | None
    smoothing_resolution: RequestQuantity | None
    context: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ProposedObservationRequest:
    target_kind: str
    geometry: str
    target_name: str | None
    position: RequestPosition | None
    setup_id: str
    setup_complete: bool | None
    intents: tuple[str, ...]
    angular_resolution: RequestQuantity | None
    representative_frequency: RequestFrequency | None
    representative_window_id: str | None
    spectral_windows: tuple[ProposedWindow, ...]
    sensitivities: tuple[ProposedSensitivity, ...]
    array_context: Mapping[str, object]
    raw_input: Mapping[str, object]
    model_version: str = "3"
    source_redshift: float | None = None
    continuum_setup_declaration: str | None = None

    @property
    def line_evaluation_scope(self) -> str:
        """Read the explicit wire scope; absence preserves legacy semantics.

        This is intentionally not a dataclass field: old request/report objects
        must retain their exact serialized shape when the field is omitted.
        """
        return self.raw_input.get("line_evaluation_scope", LINE_SCOPE_LEGACY)

    def require_legacy_input_contract(self) -> None:
        """Never run legacy science on new, separately scoped raw operands."""
        if any(k in self.raw_input for k in (
            "line_input_contract", "line_requirements", "physical_spw_evidence",
            "physical_spw_inventory_complete",
        )):
            raise ValueError("SEPARATED_INPUT_NOT_EXECUTABLE: versioned science not implemented")

    def require_implemented_line_scope(self) -> None:
        """Protect direct evaluator callers that bypass wire validation."""
        self.require_legacy_input_contract()
        if self.line_evaluation_scope != LINE_SCOPE_LEGACY:
            raise ValueError("LINE_SCOPE_NOT_IMPLEMENTED: submitted LINE requirements scope is reserved")


@dataclass(frozen=True, slots=True)
class CandidatePredicate:
    field: str
    operator: str
    quantity: RequestQuantity
    basis: str | None
    context: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class SearchOptions:
    radius: RequestQuantity | None
    sources: tuple[str, ...]
    result_limit: int | None
    predicates: tuple[CandidatePredicate, ...]
    raw_input: Mapping[str, object]
    radius_mode: str = "EXPLICIT"


@dataclass(frozen=True, slots=True)
class RequestValidationResult:
    raw_input: object
    raw_search_options: object
    request: ProposedObservationRequest | None
    search_options: SearchOptions | None
    issues: tuple[RequestIssue, ...]
    search_readiness: SearchReadiness
    validation_version: str = "8"

    @property
    def errors(self) -> tuple[RequestIssue, ...]:
        return tuple(i for i in self.issues if i.category == "ERROR")

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def can_search(self) -> bool:
        return self.search_readiness is SearchReadiness.READY
