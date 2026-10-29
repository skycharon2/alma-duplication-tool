"""Pure browser workflow policies shared by the existing /proposed route.

This is an extraction, not a new science contract or a route split.
Single Pointing retains its selected Archive/Queue sources; only the
fixed-target Mosaic browser workflow currently forces Archive-only.
"""


def is_fixed_mosaic(values):
    """Match the exact fixed-target Mosaic scope used by the browser runner."""
    return values.get("target_kind") == "FIXED" and values.get("geometry") == "MOSAIC"


def apply_browser_source_policy(values):
    """Preserve the existing POST policy without modifying Single Pointing."""
    if is_fixed_mosaic(values):
        values["sources"] = ["ARCHIVE"]


def should_enable_mosaic_v2_on_scope_change(values, rows):
    """Opt in only on a blank Mosaic switch; never reinterpret existing science.

    Input rows, continuum declarations and already-selected V2 states must
    survive a scope switch without implicit schema conversion.
    """
    return (is_fixed_mosaic(values)
            and not values.get("normal_form_version")
            and not values.get("normal_line_records")
            and not rows and not values.get("spw_rows")
            and not values.get("aggregate_windows")
            and values.get("setup_complete") != "on"
            and values.get("continuum_setup_declaration") != "on"
            and not any(values.get(key, "").strip() for key in (
                "redshift", "continuum_redshift", "representative", "aggregate")))
