"""Project interpretation of Custom CSV pointing ownership, not an OT guarantee."""
from dataclasses import dataclass

from alma_duplicate.domain.queue import QueueMosaicKind
from alma_duplicate.queue_row_beam import resolve_queue_beam_interpretation

PROFILE = 'QUEUE_CUSTOM_POINTING_OWNERSHIP_1'
LIMITATION_TITLE = 'ACA 7-m assessment not available'
LIMITATION_MESSAGE = (
    'This observation also requires ACA 7-m data. The CSV pointings are interpreted '
    'as the 12-m Array configuration. Since the corresponding 7-m pointings are '
    'not available, only the 12-m configuration has been assessed. '
    'Please keep this limitation in mind when reviewing potential duplication.'
)


@dataclass(frozen=True)
class CustomPointingOwnership:
    pointing_array: str
    ownership_basis: tuple
    requested_arrays: tuple[str, ...]
    # Resolution alone does not perform a scientific assessment.
    evaluated_arrays: tuple[str, ...]
    unassessed_arrays: tuple[str, ...]
    available_pointing_arrays: tuple[str, ...]
    profile: str = PROFILE
    interpretation_status: str = 'PROJECT_ADOPTED_NOT_OFFICIAL_EXPORT_GUARANTEE'


def resolve_custom_pointing_array(row):
    """Reuse beam evidence, restricting mixed Custom pointings to the 12-m array.

    `evaluated_arrays` starts empty; consumers record actual assessment separately.
    All beam evidence (including AR inference and anomalies) is retained verbatim.
    TP is outside the supported interferometric assessment scope.
    """
    if row.spatial.mosaic_kind is not QueueMosaicKind.CUSTOM_POINTING:
        raise ValueError('Custom Mosaic row required')
    beam = resolve_queue_beam_interpretation(row)
    owner = {'D12_ONLY': '12M', 'D7_ONLY': '7M', 'MIX_7M_12M': '12M'}.get(
        beam.classification, 'UNKNOWN')
    requested = {'D12_ONLY': ('12M',), 'D7_ONLY': ('7M',),
                 'MIX_7M_12M': ('7M', '12M')}.get(beam.classification,
                    ('7M', 'UNKNOWN') if row.request.use_7m is True else ('UNKNOWN',))
    available = () if owner == 'UNKNOWN' else (owner,)
    basis = beam.details(row) + (
        ('ownership_rule', 'MIXED_CUSTOM_POINTS_INTERPRETED_AS_12M' if beam.classification == 'MIX_7M_12M'
         else 'CUSTOM_POINTS_FOLLOW_SINGLE_ARRAY_INFERENCE' if owner != 'UNKNOWN'
         else 'CUSTOM_POINTING_OWNERSHIP_UNRESOLVED'),)
    return CustomPointingOwnership(owner, basis, requested, (), requested, available)
