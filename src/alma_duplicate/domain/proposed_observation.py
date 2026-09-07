"""Source-independent proposed observations; construct through the validator.

Frozen values describe supplied evidence, not confirmed observing feasibility or
duplication. Missing scientific information is represented by None/UNKNOWN.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class SearchReadiness(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class RequestIssue:
    category: str  # ERROR, MISSING, CAPABILITY
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
    model_version: str = "1"


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


@dataclass(frozen=True, slots=True)
class RequestValidationResult:
    raw_input: object
    raw_search_options: object
    request: ProposedObservationRequest | None
    search_options: SearchOptions | None
    issues: tuple[RequestIssue, ...]
    search_readiness: SearchReadiness
    validation_version: str = "3"

    @property
    def errors(self) -> tuple[RequestIssue, ...]:
        return tuple(i for i in self.issues if i.category == "ERROR")

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def can_search(self) -> bool:
        return self.search_readiness is SearchReadiness.READY
