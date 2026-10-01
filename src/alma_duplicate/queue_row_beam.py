"""Versioned Queue beam hypotheses; raw source evidence is never rewritten."""

from dataclasses import dataclass
import math
from types import MappingProxyType

PROFILE = "QUEUE_ARRAY_BEAM_INFERENCE_2"
DECISION_REF = "docs/evidence/queue_array_beam_inference_decision_2026-10-01.md"
FIELD = "standAlone_ACA"
# Cycle 13 representative GHz and 7-m resolution in arcsec. No frequency scaling.
ACA_7M_THRESHOLDS = MappingProxyType(
    {
        "1": (40, 31.8),
        "2": (75, 16.9),
        "3": (100, 12.7),
        "4": (150, 8.47),
        "5": (185, 6.87),
        "6": (230, 5.52),
        "7": (345, 3.68),
        "8": (460, 2.76),
        "9": (650, 1.95),
        "10": (870, 1.46),
    }
)


def _threshold(band):
    # The typed Queue band retains its source label, e.g. ALMA_RB_07.
    labels = {f"ALMA_RB_{int(key):02d}": key for key in ACA_7M_THRESHOLDS}
    key = band.strip()
    return ACA_7M_THRESHOLDS.get(labels.get(key, key))


@dataclass(frozen=True, slots=True)
class QueueBeamInterpretation:
    classification: str
    diameters_m: tuple[float, ...]
    field_status: str
    standalone: bool | None
    interpretation_kind: str
    raw_value: str
    reasons: tuple[str, ...]
    anomalies: tuple[str, ...]

    @property
    def diameter_m(self):
        """A single diameter exists only for an unambiguous single hypothesis."""
        return self.diameters_m[0] if len(self.diameters_m) == 1 else None

    @property
    def source(self):
        return ";".join(self.reasons)

    def details(self, row):
        threshold = _threshold(row.group_key.band)
        ar = row.request.requested_angular_resolution_arcsec
        return (
            ("row_beam_profile", PROFILE),
            ("beam_classification", self.classification),
            ("beam_diameters_m", ",".join(str(d) for d in self.diameters_m)),
            ("diameter_source", self.source),
            ("standalone_aca_field", self.field_status),
            ("standalone_aca_raw", self.raw_value),
            (
                "standalone_aca_interpretation",
                "UNKNOWN" if self.standalone is None else str(self.standalone).lower(),
            ),
            ("standalone_aca_interpretation_kind", self.interpretation_kind),
            ("use_7m_requested", str(row.request.use_7m).lower()),
            ("use_tp_requested", str(row.request.use_tp).lower()),
            (
                "requested_components",
                ",".join(
                    name
                    for flag, name in (
                        (row.request.use_7m, "ACA_7M"),
                        (row.request.use_tp, "ACA_TP"),
                    )
                    if flag is True
                )
                or "NONE",
            ),
            ("requested_component_anomaly", ";".join(self.anomalies) or "NONE"),
            (
                "requested_angular_resolution_arcsec",
                "UNKNOWN" if ar is None else str(ar.value),
            ),
            ("requested_angular_resolution_raw", "" if ar is None else ar.raw_text),
            ("band", row.group_key.band),
            (
                "aca_7m_threshold_arcsec",
                "UNKNOWN" if threshold is None else str(threshold[1]),
            ),
            (
                "threshold_representative_frequency_ghz",
                "UNKNOWN" if threshold is None else str(threshold[0]),
            ),
            ("reference_frequency_raw", row.raw_row.value("Ref.Frequency")),
            ("threshold_frequency_scaling", "NONE_FIXED_BAND_TABLE"),
        )


def resolve_queue_beam_interpretation(row):
    """Apply operational evidence first, and AR inference only to an absent field."""
    raw = row.raw_row
    count = raw.declared_columns.count(FIELD)
    token = raw.value(FIELD) if count else ""
    valid = count == 1 and token.strip().lower() in ("true", "false")
    state = "ABSENT" if not count else "PRESENT" if valid else "INVALID"
    standalone = token.strip().lower() == "true" if valid else None
    use7, tp = row.request.use_7m, row.request.use_tp
    anomalies = []
    if standalone is True and use7 is False:
        anomalies.append("STANDALONE_WITHOUT_7M_REQUEST")
    if tp is True and use7 is False:
        anomalies.append("TP_WITHOUT_7M")

    def result(diameters, reasons, kind=None):
        classification = {
            (7.0,): "D7_ONLY",
            (12.0,): "D12_ONLY",
            (7.0, 12.0): "MIX_7M_12M",
            (): "UNRESOLVED",
        }[diameters]
        return QueueBeamInterpretation(
            classification,
            diameters,
            state,
            standalone,
            kind or ("SOURCE_PROVIDED" if valid else "SUPERVISOR_ADOPTED_INFERENCE"),
            token,
            tuple(reasons),
            tuple(anomalies),
        )

    if state == "INVALID":
        return result((), ("INVALID_STANDALONE_VALUE",), "UNRESOLVED")
    # Parsed flags must be actual booleans, never strings or truthy numbers.
    if type(use7) is not bool or type(tp) is not bool:
        return result((), ("INVALID_ARRAY_FLAGS",), "UNRESOLVED")
    tp_reason = ("TP_12M_REQUESTED",) if tp else ()
    if standalone is True:
        return result(
            (7.0, 12.0) if tp else (7.0,), ("SOURCE_STANDALONE_ACA",) + tp_reason
        )
    if standalone is False:
        return result(
            (7.0, 12.0) if use7 else (12.0,),
            ("SOURCE_NON_STANDALONE",)
            + (("ACA_7M_REQUESTED",) if use7 else ())
            + tp_reason,
        )
    reasons = ("STANDALONE_FIELD_ABSENT",)
    if not use7:
        return result((12.0,), reasons + ("ACA_7M_NOT_REQUESTED",) + tp_reason)
    reasons += ("ACA_7M_REQUESTED",)
    if tp:
        return result((7.0, 12.0), reasons + tp_reason)
    ar = row.request.requested_angular_resolution_arcsec
    threshold = _threshold(row.group_key.band)
    if (
        ar is None
        or ar.canonical_unit != "arcsec"
        or isinstance(ar.value, bool)
        or not isinstance(ar.value, (int, float))
        or not math.isfinite(ar.value)
        or ar.value <= 0
        or threshold is None
    ):
        return result(
            (), reasons + ("ACA_7M_INFERENCE_EVIDENCE_UNAVAILABLE",), "UNRESOLVED"
        )
    if ar.value < threshold[1]:
        return result(
            (7.0, 12.0),
            reasons
            + (
                "REQUESTED_RESOLUTION_FINER_THAN_7M_THRESHOLD",
                "MAIN_12M_REQUIRED_BY_SUPERVISOR_INFERENCE",
            ),
        )
    return result(
        (7.0,),
        reasons + ("REQUESTED_RESOLUTION_7M_COMPATIBLE",),
        "7M_COMPATIBLE_INFERENCE",
    )


# Compatibility for single-diameter consumers: MIX deliberately has no scalar D.
resolve_queue_primary_beam_diameter = resolve_queue_beam_interpretation
