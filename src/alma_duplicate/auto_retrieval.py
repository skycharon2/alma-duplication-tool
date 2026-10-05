"""Conservative, versioned retrieval scope; never a scientific position verdict."""
import math

from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.domain.proposed_observation import RequestQuantity

METHOD = 'auto_fixed_single_1'
# This is an explicit supported envelope, not an inferred property of unknown rows.
MIN_CANDIDATE_FREQUENCY_GHZ = 35.0
MIN_DISH_DIAMETER_M = 7.0


def automatic_radius():
    """Outward-rounded half-FWHM envelope for supported 7/12-m candidates."""
    value = primary_beam_fwhm_deg(MIN_CANDIDATE_FREQUENCY_GHZ, MIN_DISH_DIAMETER_M) / 2
    # Keep the serialized ADQL decimal outside the physical bound as well.
    value = math.ceil(value * 1e10) / 1e10
    return RequestQuantity(value, 'deg', None, 'deg', METHOD)


def automatic_scope():
    """Fresh JSON-ready provenance, also usable by offline browser rendering."""
    return {
        'mode': 'AUTO', 'method_version': METHOD,
        'archive_strategy': 'CENTER_CONE',
        'archive_radius_deg': automatic_radius().value,
        'minimum_candidate_frequency_ghz': MIN_CANDIDATE_FREQUENCY_GHZ,
        'minimum_diameter_m': MIN_DISH_DIAMETER_M,
        'beam_coefficient': 1.13,
        'queue_strategy': 'ALL_SUPPLIED_ROWS',
        'limitations': [
            'FIXED_SINGLE_POINTING_ONLY',
            'ARCHIVE_BOUND_COVERS_FREQUENCY_GE_35_GHZ_AND_DIAMETER_GE_7_M',
            'ARCHIVE_UNKNOWN_OR_LOWER_FREQUENCY_OUTSIDE_CONE_NOT_COVERED',
            'ARCHIVE_MISSING_CENTERS_AND_MOSAIC_EXTENTS_NOT_COVERED',
            'QUEUE_SCOPE_IS_SUPPLIED_FILE',
            'POSITION_IS_EVALUATED_SEPARATELY_WITH_CANDIDATE_EVIDENCE',
            'NO_SEARCH_WIDE_ABSENCE_VERDICT',
        ],
    }
