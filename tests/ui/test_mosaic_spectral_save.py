"""Optional Mosaic frequency evidence never changes saved scientific decisions."""
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace

from alma_duplicate import mosaic_spectral_evidence as saved


@dataclass
class Reference:
    source: str
    raw_row_id: str
    source_record_id: str = 'archive-source'


@dataclass
class Support:
    raw_row_id: str
    parse_result: dict


@dataclass
class ArchiveEvidence:
    support_evidence: Support


def test_archive_setup_is_attached_only_to_matching_bound_context(monkeypatch):
    monkeypatch.setattr(saved, 'ArchiveContextEvidence', ArchiveEvidence)
    monkeypatch.setattr(saved, '_display_identity', lambda context: {'Member OUS': 'm', 'ASDM': 'a', 'Target': 't'})
    context = SimpleNamespace(context_id='c1', reference=Reference('ARCHIVE', 'raw-1'),
        evidence=ArchiveEvidence(Support('raw-1', {'components': []})))
    report = dict(contexts=[dict(context_id='c1', branches=[dict(status='CRITERIA_MET')],
                                 criteria=[dict(criterion_id='POS-MOSAIC', outcome='SATISFIED')]),
                            dict(context_id='c2', branches=[dict(status='CRITERIA_NOT_MET')])])
    baseline = deepcopy(report)
    displays = saved.attach_archive_spectral_setups(report, [context])
    assert report == baseline  # Captured scientific contexts must remain exact.
    assert set(displays) == {'c1'}
    assert displays['c1']['spectral_setup_display']['evidence']['raw_row_id'] == 'raw-1'
    assert displays['c1']['source_reference']['raw_row_id'] == 'raw-1'
    assert 'c2' not in displays
    context.evidence.support_evidence.raw_row_id = 'foreign'
    second = dict(contexts=[dict(context_id='c1', branches=[dict(status='CRITERIA_MET')])])
    second_before = deepcopy(second)
    assert saved.attach_archive_spectral_setups(second, [context]) == {}
    assert second == second_before


@dataclass
class Regular:
    spws: tuple


@dataclass
class Spw:
    number: int = 25
    lower_sky_frequency_ghz: float = 689.0
    upper_sky_frequency_ghz: float = 692.0
    usable_lower_sky_frequency_ghz: float | None = None
    usable_upper_sky_frequency_ghz: float | None = None


def test_queue_setup_uses_exact_snapshot_and_concordant_regular_rows(monkeypatch):
    monkeypatch.setattr(saved, 'RegularSpwEvidence', Regular)
    spectral = Regular((Spw(),))
    inputs = [SimpleNamespace(raw_row=SimpleNamespace(row_id=SimpleNamespace(value=i)), spectral=spectral)
              for i in ('sha:1', 'sha:2')]
    parsed = SimpleNamespace(snapshot=SimpleNamespace(snapshot_sha256='sha'), row_inputs=inputs)
    candidate = dict(candidate_id='candidate-a',
        source_rows=[dict(source_row_id='sha:1'), dict(source_row_id='sha:2')],
        science=dict(representative_source_row_id='sha:1',
                     variants=[dict(branches=[dict(truth='TRUE')])]))
    report = dict(candidates=[candidate])
    before = deepcopy(candidate['science']['variants'])
    saved.attach_queue_spectral_setups(report, parsed)
    assert candidate['science']['variants'] == before
    display = candidate['science']['spectral_setup_display']
    assert display['source_row_ids'] == ['sha:1', 'sha:2']
    assert display['snapshot_sha256'] == 'sha'
    assert display['spws'][0]['nominal_low_ghz'] == 689.0
    del candidate['science']['spectral_setup_display']
    inputs[1].spectral = Regular((Spw(number=26),))
    saved.attach_queue_spectral_setups(report, parsed)
    assert 'spectral_setup_display' not in candidate['science']
