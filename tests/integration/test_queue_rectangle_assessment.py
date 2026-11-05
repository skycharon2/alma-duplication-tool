"""Rectangle through the standard lazy-source assessment entry point."""
import json
import pytest
from alma_duplicate.assessment import assess_observation, AssessmentSources, AssessmentOptions
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from tests.integration.test_queue_rectangle_science import candidate
from tests.integration.test_queue_custom_science import request, pointings, science


def run(parsed=None, proposed=None, **kwargs):
    req,payload=request()
    payload['search_options']['sources']=['QUEUE']
    return assess_observation(**payload,queue_rectangle=proposed or pointings(req),
        sources=kwargs.pop('sources',AssessmentSources(queue_loader=lambda: parsed or candidate())),**kwargs)


@pytest.mark.parametrize('changes,expected',[({},'TRUE'),({'Ref.Frequency':'100'},'FALSE'),
    ({'Mos. Coord.':'galactic'},'UNKNOWN')])
def test_standard_assessment(changes,expected):
    r=run(candidate(changes))
    d=r.document
    assert r.status=='COMPLETED' and r.validation.can_search
    assert d['schema_version']=='queue_rectangle_assessment_1'
    assert d['report_kind']=='QUEUE_RECTANGLE_MOSAIC'
    assert len(d['candidates'])==2
    assert science(d)['branches'][0]['truth']==expected
    assert d['sources']['QUEUE']['status']=='COMPLETE'
    assert not d['evaluation_configuration']['single_point_radius_applied']
    assert d['model_status']=='PROJECT_ACCEPTED'
    assert d['candidates'][0]['science']['model_status'] in ('PROJECT_ACCEPTED', 'UNRESOLVED')
    json.dumps(d,allow_nan=False)


def forbidden():
    pytest.fail('must not load source')


@pytest.mark.parametrize('kwargs',[{'queue_custom':{}},{'mosaic':object()},
    {'report_detail':'matches'},{'options':AssessmentOptions(queue_line=True)}])
def test_configuration_rejected_before_loading(kwargs):
    with pytest.raises(ValueError):
        run(sources=AssessmentSources(queue_loader=forbidden),**kwargs)


@pytest.mark.parametrize('loader',[None,lambda:parse_queue_csv_bytes(b'invalid\n')])
def test_unavailable_source(loader):
    r=run(sources=AssessmentSources(queue_loader=loader))
    assert r.status=='SOURCES_UNAVAILABLE'
    assert r.document['candidates']==[]
    assert r.document['duplication_status']=='NO_SEARCH_WIDE_ABSENCE_CLAIM'


def test_failed_loader_and_invalid_request():
    def failed():raise OSError('missing')
    assert run(sources=AssessmentSources(queue_loader=failed)).status=='SOURCES_UNAVAILABLE'
    r=assess_observation({'target_kind':'INVALID'},{},queue_rectangle={},
        sources=AssessmentSources(queue_loader=forbidden))
    assert r.status=='REQUEST_NOT_SEARCH_READY'


def test_independent_configurations_and_7m_only_match():
    from tests.integration.test_candidate_search import queue_rows
    from alma_duplicate.geometry import primary_beam_fwhm_deg
    rows=[dict(zip(r.raw_row.declared_columns,r.raw_row.raw_values)) for r in candidate().row_inputs]
    rows[1]['Ref.Frequency']='100'
    req,_=request()
    p=pointings(req)
    p['points'][0]['dec_deg']+=(primary_beam_fwhm_deg(230,7)+primary_beam_fwhm_deg(230,12))/4
    d=run(queue_rows(*rows),proposed=p).document
    assert len({c['geometry']['source_row_id'] for c in d['candidates']})==2
    assert sorted(c['science']['branches'][0]['truth'] for c in d['candidates'])==['FALSE','TRUE']
    matched=next(c for c in d['candidates'] if c['science']['branches'][0]['truth']=='TRUE')
    assert matched['science']['matching_arrays_by_intent']['CONTINUUM']==[7.]
