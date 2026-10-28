"""Step 03b-A: independently parse LINE requirements and physical SPW evidence.

The adapter constructs separate, immutable operands with existing unit parsers.
It does *not* run science, claim LINE enumeration completeness, or translate
physical inventory completeness into ``setup_complete``. Shared entrypoints
reject this wire contract until the versioned evaluator is implemented.
"""
from dataclasses import dataclass

from alma_duplicate.domain.proposed_observation import (
    CONTINUUM_SETUP_DECLARATION, ProposedSensitivity, ProposedWindow,
)
from alma_duplicate.proposed_line import prepare_line_window

SEPARATED_INPUT_CONTRACT = "SEPARATE_REQUIREMENTS_AND_SPW_EVIDENCE_V1"
NEW_INPUT_FIELDS = frozenset({
    "line_input_contract", "line_requirements", "physical_spw_evidence",
    "physical_spw_inventory_complete",
})
LEGACY_INPUT_FIELDS = frozenset({
    "spectral_windows", "sensitivities", "setup_complete",
    "line_requirement_window_ids",
})


@dataclass(frozen=True, slots=True)
class PhysicalSpwLink:
    spw_id: str
    line_requirement_id: str | None


@dataclass(frozen=True, slots=True)
class SeparatedSetupOperands:
    """Typed operands; the collections must never be concatenated for science."""
    line_windows: tuple[ProposedWindow, ...]
    line_sensitivities: tuple[ProposedSensitivity, ...]
    physical_spw_windows: tuple[ProposedWindow, ...]
    physical_links: tuple[PhysicalSpwLink, ...]
    physical_inventory_complete: bool

    @property
    def continuum_window_evidence(self) -> tuple[ProposedWindow, ...]:
        """Exactly one window per physical SPW ID, never cloned for a LINE link."""
        return self.physical_spw_windows

    @property
    def line_comparison_operands(self):
        """LINE-only operands; never include bandwidth-only physical SPWs."""
        return self.line_windows, self.line_sensitivities


def parse_separated_setup(validator, raw):
    """Validate and adapt one snapshot using the shared validator's unit rules.

    Called at the shared request-validation boundary before any providers.
    A returned object is *not* an authorization to execute formal science.
    """
    v = validator
    allowed = {
        "target_kind", "geometry", "target_name", "position", "setup_id",
        "intents", "angular_resolution", "representative_frequency",
        "representative_window_id", "array_context", "source_redshift",
        "continuum_setup_declaration", "line_evaluation_scope",
        *NEW_INPUT_FIELDS, *LEGACY_INPUT_FIELDS,
    }
    obj = v.obj(raw, "request", allowed)
    contract = v.enum(
        obj.get("line_input_contract"), "request.line_input_contract",
        {SEPARATED_INPUT_CONTRACT},
    )
    for name in sorted(LEGACY_INPUT_FIELDS.intersection(obj)):
        v.error(
            "MIXED_INPUT_CONTRACTS", f"request.{name}",
            "Separated input must not include legacy window, sensitivity, or setup_complete fields.",
        )
    if "line_evaluation_scope" in obj:
        v.error(
            "MIXED_INPUT_CONTRACTS", "request.line_evaluation_scope",
            "The separated input contract does not opt into either legacy or V2 LINE aggregation.",
        )
    for key in ("line_requirements", "physical_spw_evidence", "physical_spw_inventory_complete"):
        if key not in obj:
            v.error("REQUIRED_FIELD", f"request.{key}", "Field required by separated input contract.")
    for key in ("line_requirements", "physical_spw_evidence"):
        if key in obj and type(obj[key]) is not tuple:
            v.error("INVALID_SHAPE", f"request.{key}", "Expected a list.")
    inventory_complete = obj.get("physical_spw_inventory_complete")
    if type(inventory_complete) is not bool:
        v.error("INVALID_TYPE", "request.physical_spw_inventory_complete",
                "Explicit Boolean is required; it refers only to physical SPWs.")
        inventory_complete = False

    v.enum(obj.get("target_kind"), "request.target_kind", {"FIXED", "MOVING", "SUN"})
    v.enum(obj.get("geometry"), "request.geometry", {"SINGLE_POINTING", "MOSAIC"})
    selected_intents = v.names(obj.get("intents"), "request.intents", {"LINE", "CONTINUUM"})
    if obj.get("continuum_setup_declaration") is not None:
        v.enum(obj["continuum_setup_declaration"],
               "request.continuum_setup_declaration", {CONTINUUM_SETUP_DECLARATION})
    setup_id = v.text(obj.get("setup_id"), "request.setup_id", required=True)
    redshift = None
    if obj.get("source_redshift") is not None:
        redshift = v.number(obj["source_redshift"], "request.source_redshift")
        if redshift is not None and redshift <= -1:
            v.error("INVALID_REDSHIFT", "request.source_redshift", "Require z > -1.")

    line_windows = []
    line_sensitivities = []
    line_ids = set()
    for i, item in enumerate(v.items(obj.get("line_requirements"), "request.line_requirements")):
        path = f"request.line_requirements[{i}]"
        entry = v.obj(item, path, {
            "requirement_id", "window_center", "correlator_mode",
            "spectral_resolution", "rms",
        })
        identifier = v.text(entry.get("requirement_id"), path + ".requirement_id", required=True)
        if identifier is not None:
            if identifier in line_ids:
                v.error("DUPLICATE_ID", path + ".requirement_id",
                        "LINE requirement IDs must be unique.")
            line_ids.add(identifier)
        # A requirement is a correlator WINDOW, not a molecular rest line.
        if entry.get("window_center") is None:
            v.error("LINE_CENTER_REQUIRED", path + ".window_center",
                    "Supply the requested correlator-window centre frequency.")
        if entry.get("spectral_resolution") is None:
            v.error("LINE_RESOLUTION_REQUIRED", path + ".spectral_resolution",
                    "Supply the planned resolution at which RMS is specified.")
        if entry.get("rms") is None:
            v.error("LINE_RMS_REQUIRED", path + ".rms", "Supply this LINE requirement's RMS.")
        mode = v.enum(entry.get("correlator_mode"), path + ".correlator_mode", {"FDM", "TDM"})
        # Existing canonical parsing checks units, references and positivity.
        window = v.window({
            "window_id": identifier,
            "center": entry.get("window_center"),
            "correlator_mode": mode,
            "spectral_resolution": entry.get("spectral_resolution"),
        }, path)
        sensitivity = v.sensitivity({
            "sensitivity_id": f"line:{identifier}",
            "purpose": "LINE", "scope": "WINDOW", "window_ids": (identifier,),
            "basis": "SMOOTHED", "rms": entry.get("rms"),
            "smoothing_resolution": entry.get("spectral_resolution"),
        }, path + ".sensitivity", setup_id, {identifier: window})
        line_windows.append(window)
        line_sensitivities.append(sensitivity)
        prepared = prepare_line_window(window, (sensitivity,), redshift)
        if prepared.sky_frequency_ghz_exact is None:
            v.error("LINE_FREQUENCY_UNRESOLVED", path + ".window_center",
                    "Supply a SKY centre or a REST centre with a usable source redshift.")
        if prepared.planned_resolution_kms_exact is None:
            v.error("LINE_RESOLUTION_UNRESOLVED", path + ".spectral_resolution",
                    "Planned LINE resolution cannot be prepared.")
    if "LINE" in selected_intents and not line_windows:
        v.error("LINE_REQUIREMENT_REQUIRED", "request.line_requirements",
                "A selected LINE purpose requires at least one submitted requirement.")

    physical_windows = []
    physical_links = []
    spw_ids = set()
    linked_line_ids = set()
    for i, item in enumerate(v.items(obj.get("physical_spw_evidence"), "request.physical_spw_evidence")):
        path = f"request.physical_spw_evidence[{i}]"
        entry = v.obj(item, path, {
            "spw_id", "linked_line_requirement_id", "center", "bandwidth", "bandwidth_kind",
        })
        spw_id = v.text(entry.get("spw_id"), path + ".spw_id", required=True)
        if spw_id is not None:
            if spw_id in spw_ids:
                v.error("DUPLICATE_ID", path + ".spw_id", "Physical SPW IDs must be unique.")
            spw_ids.add(spw_id)
        linked = v.text(entry.get("linked_line_requirement_id"),
                        path + ".linked_line_requirement_id")
        if linked is not None:
            if linked not in line_ids:
                v.error("DANGLING_REFERENCE", path + ".linked_line_requirement_id",
                        "Physical SPW link must reference an existing LINE requirement.")
            if linked in linked_line_ids:
                v.error("AMBIGUOUS_PHYSICAL_SPW_LINK", path + ".linked_line_requirement_id",
                        "A LINE requirement may link to at most one physical SPW record.")
            linked_line_ids.add(linked)
        if entry.get("bandwidth") is not None and entry.get("bandwidth_kind") is None:
            v.error("BANDWIDTH_KIND_REQUIRED", path + ".bandwidth_kind",
                    "State whether supplied bandwidth is USABLE, NOMINAL, or UNKNOWN.")
        if entry.get("bandwidth") is None and entry.get("bandwidth_kind") is not None:
            v.error("BANDWIDTH_WITHOUT_VALUE", path + ".bandwidth_kind",
                    "Do not declare bandwidth semantics without a bandwidth.")
        physical_windows.append(v.window({
            "window_id": spw_id, "center": entry.get("center"),
            "bandwidth": entry.get("bandwidth"),
            "bandwidth_kind": entry.get("bandwidth_kind", "UNKNOWN"),
            "correlator_mode": "UNKNOWN",
        }, path))
        physical_links.append(PhysicalSpwLink(spw_id, linked))
    # No frequency-based merging, no cloning linked windows, no implicit line completeness.
    # The evaluation gate in request_validation prevents these operands being
    # passed to the old OR aggregator until Step 04 has its own method version.
    if contract is None:
        return None
    return SeparatedSetupOperands(
        tuple(line_windows), tuple(line_sensitivities), tuple(physical_windows),
        tuple(physical_links), inventory_complete,
    )
