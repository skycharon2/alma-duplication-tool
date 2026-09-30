"""Display projections of stored criteria; no scientific calculation or aggregation."""

LABELS = {
    "POS-SINGLE": "Position", "ANGULAR": "Angular resolution",
    "CONT-SETUP": "Proposed continuum setup", "CONT-FREQ": "Representative frequency",
    "CONT-RMS": "Aggregate RMS", "LINE-FDM": "Correlator mode",
    "LINE-COVERAGE": "Frequency coverage",
    "LINE-RESOLUTION-COMPATIBILITY": "Spectral resolution", "LINE-RMS": "LINE RMS",
}

# Explicit units only. Unknown keys retain their backend names with no inferred unit.
DERIVED = {
    "separation_deg": ("Angular separation", "deg"),
    "candidate_radius_deg": ("Candidate beam radius", "deg"),
    "candidate_fwhm_deg": ("Candidate beam FWHM", "deg"),
    "candidate_frequency_ghz": ("Candidate beam frequency", "GHz"),
    "antenna_diameter_m": ("Antenna diameter", "m"),
    "candidate_ra_deg": ("Candidate RA", "deg"),
    "candidate_dec_deg": ("Candidate Dec", "deg"),
    "proposal_ra_deg": ("Proposed RA", "deg"),
    "proposal_dec_deg": ("Proposed Dec", "deg"),
    "sky_frequency_ghz": ("Prepared proposed sky frequency", "GHz"),
    "interval_low_ghz": ("Candidate interval lower bound", "GHz"),
    "interval_high_ghz": ("Candidate interval upper bound", "GHz"),
    "archive_resolution_kms": ("Archive spectral resolution", "km/s"),
    "planned_resolution_kms": ("Planned spectral resolution", "km/s"),
    "planned_resolution_mhz": ("Planned spectral resolution at the line frequency", "MHz"),
    "queue_resolution_mhz": ("Queue spectral resolution", "MHz"),
    "sigma_10kms_mjy_beam": ("Archive RMS at 10 km/s", "mJy/beam"),
    "sigma_at_plan_mjy_beam": ("Archive RMS at planned resolution", "mJy/beam"),
    "sigma_comp_mjy_beam": ("Archive RMS after angular correction", "mJy/beam"),
    "sigma_requested_mjy_beam": ("Requested RMS", "mJy/beam"),
    "queue_reference_width_mhz": ("Queue reference noise bandwidth", "MHz"),
    "queue_rms_at_planned_resolution_mjy": ("Queue RMS at planned resolution", "mJy"),
    "comparable_queue_rms_mjy": ("Queue RMS after angular correction", "mJy"),
    "theta_plan_arcsec": ("Planned angular resolution", "arcsec"),
    "theta_archive_arcsec": ("Archive angular resolution", "arcsec"),
    "theta_queue_arcsec": ("Queue angular resolution", "arcsec"),
    "reference_bandwidth_mhz": ("Queue reference noise bandwidth", "MHz"),
    "aggregate_bandwidth_mhz": ("Queue aggregate usable bandwidth", "MHz"),
    "aggregate_rms_mjy": ("Queue aggregate RMS", "mJy"),
    "qualifying_windows": ("Qualifying windows", ""),
    "unresolved_windows": ("Unresolved windows", ""),
    "threshold_ghz": ("Usable bandwidth threshold", "GHz"),
    "factor": ("Comparison factor", ""), "max_factor": ("Maximum factor", ""),
}


def criterion_view(record):
    """Keep the original record intact and project only explicitly stored evidence."""
    details = dict(record.get("details", []))
    derived = dict(record.get("derived", []))
    proposed, candidate = record.get("proposed"), record.get("candidate")
    if record["criterion_id"] == "LINE-FDM":
        proposed = {"value": details.get("proposed_mode"), "unit": ""}
        candidate = {"value": details.get("candidate_mode", details.get("queue_mode")), "unit": ""}
    if record["criterion_id"] == "LINE-COVERAGE" and candidate is None:
        low, high = derived.get("interval_low_ghz"), derived.get("interval_high_ghz")
        if low is not None and high is not None:
            candidate = {"value": f"{low} – {high}", "unit": "GHz",
                         "semantics": "Candidate interval from backend"}
    return {
        "record": record, "label": LABELS.get(record["criterion_id"], record["criterion_id"]),
        "proposed": proposed, "candidate": candidate,
        "derived": [
            {"key": key, "label": DERIVED.get(key, (key, ""))[0],
             "unit": DERIVED.get(key, (key, ""))[1], "value": value}
            for key, value in record.get("derived", [])
        ],
    }


def pair_binding(pair):
    """Expose the exact binding, including zero-valued SPW indices."""
    ref = pair["attempt"].get("reference") or {}
    fields = [("Proposed setup", ref.get("proposed_setup_id")),
              ("Proposed window", ref.get("proposed_window_id")),
              ("Proposed sensitivity", ref.get("proposed_sensitivity_id"))]
    association = ref.get("candidate_association") or {}
    if association:
        fields.extend((key, value) for key, value in (association.get("context") or {}).items())
        fields.extend((key, association.get(key)) for key in ("spw_token", "spw_index"))
    fields.extend((key, ref.get(key)) for key in ("source_row_id", "spw_number", "snapshot_sha256"))
    component = ref.get("candidate_component") or {}
    fields.extend((key, value) for key, value in component.items())
    return [(key, value) for key, value in fields if value is not None]
