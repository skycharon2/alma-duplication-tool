"""Versioned Portal row-beam interpretation, distinct from array components."""

from dataclasses import dataclass

PROFILE = "QUEUE_CYCLE13_PORTAL_ROW_BEAM_1"
DECISION_REF = "docs/evidence/queue_row_beam_decision_2026-09-24.md"
FIELD = "standAlone_ACA"


@dataclass(frozen=True, slots=True)
class QueueRowBeam:
    diameter_m: float | None
    source: str
    field_status: str
    standalone: bool | None
    interpretation_kind: str
    raw_value: str

    def details(self, row):
        return (
            ("row_beam_profile", PROFILE),
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
            (
                "requested_component_anomaly",
                "TP_WITHOUT_7M"
                if row.request.use_tp is True and row.request.use_7m is False
                else "NONE",
            ),
        )


def resolve_queue_primary_beam_diameter(row):
    """Read operational evidence only; missing-column fallback is an assumption.

    Present but empty/invalid/duplicate fields never use the absent-column path.
    Auxiliary requested-array flags do not select the row diameter.
    """
    raw = row.raw_row
    count = raw.declared_columns.count(FIELD)
    if not count:
        return QueueRowBeam(
            12.0,
            "CYCLE13_PORTAL_HELPER_FALLBACK",
            "ABSENT",
            False,
            "PORTAL_HELPER_ASSUMPTION",
            "",
        )
    token = raw.value(FIELD)
    if count == 1 and token.strip().lower() in ("true", "false"):
        standalone = token.strip().lower() == "true"
        return QueueRowBeam(
            7.0 if standalone else 12.0,
            "SOURCE_STANDALONE_ACA" if standalone else "SOURCE_NON_STANDALONE",
            "PRESENT",
            standalone,
            "SOURCE_PROVIDED",
            token,
        )
    return QueueRowBeam(
        None, "INVALID_STANDALONE_VALUE", "INVALID", None, "UNRESOLVED", token
    )
