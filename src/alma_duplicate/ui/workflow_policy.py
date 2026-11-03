"""Browser source and geometry policies for observation forms."""


def initial_mosaic_values(initial_values):
    """Start Mosaic with both sources selected.

    Explicit posted forms preserve their submitted input contract.
    """
    return initial_values | {
        "target_kind": "FIXED", "geometry": "MOSAIC",
        "sources": ["ARCHIVE", "QUEUE"], "normal_form_version": "2",
    }


def is_fixed_mosaic(values):
    """Match the exact fixed-target Mosaic scope used by the browser runner."""
    return values.get("target_kind") == "FIXED" and values.get("geometry") == "MOSAIC"


def apply_browser_source_policy(values):
    """Keep Mosaic source choices in display order, including an empty selection."""
    if is_fixed_mosaic(values):
        values["sources"] = [s for s in ("ARCHIVE", "QUEUE") if s in values.get("sources", [])]



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
