"""Confirmed numerical acceptance, distinct from real Archive capture evidence."""
from copy import deepcopy
from dataclasses import replace
import itertools
import json
from pathlib import Path
import pytest
from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.cli.evaluate import main
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.comparison import build_archive_contexts
from alma_duplicate.primary_beam import primary_beam_fwhm_deg
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.aggregation import Truth as T, three_and, three_or, aggregate_continuum
from alma_duplicate.rules.continuum import evaluate_continuum_frequency, evaluate_continuum_rms
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.model import CriterionOutcome as O, MethodApproval, EvaluationStatus as E
from alma_duplicate.rules.position_single import evaluate_position_single
from alma_duplicate.search_plan import build_search_plan
from alma_duplicate.spatial import adapt_spatial
from tests.integration.test_search_plan_spatial import archive
ROOT=Path(__file__).parents[2]
EXAMPLE=ROOT/'examples/confirmed_continuum'

def payload():
    return json.loads((EXAMPLE/'request.json').read_text())

def validated(p=None):
    p=p or payload();v=validate_proposed_observation(p['request'],p['search_options'])
    assert v.is_valid and v.can_search,v.issues
    return v

def case(p=None,**changes):
    v=validated(p)
    values=dict(s_ra=201.3665,s_dec=-43.0185,frequency=240.,spatial_resolution=.45,
                cont_sensitivity_bandwidth=.15,region='CIRCLE ICRS 201.3665 -43.0185 0.1')
    values.update(changes);source,context=archive(build_search_plan(v),**values)
    return v.request,context,adapt_spatial(context,source)

def test_guide_A_cli_full_pipeline(tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *a,**k:pytest.fail('network'))
    out=tmp_path/'report.json'
    assert main(['--request',str(EXAMPLE/'request.json'),'--archive-replay',
                 str(EXAMPLE/'archive/manifest.json'),'--output',str(out)])==0
    d=json.loads(out.read_text())
    assert d['report_version']=='3' and d['evaluation_version']=='4'
    assert d['assessment']=='NOT_AGGREGATED'
    assert d['evaluation_scope']['total_retained']==d['evaluation_scope']['evaluated_contexts']==4
    assert d['evaluation_scope']['shown_candidates']==1
    assert d['sources']['ARCHIVE']['replay']['fixture_kind']=='SYNTHETIC_NUMERIC_ACCEPTANCE'
    assert [c['branches'][0]['status'] for c in d['context_evaluations']]==[
        'CRITERIA_MET','CRITERIA_NOT_MET','INDETERMINATE','CRITERIA_NOT_MET']
    first=d['context_evaluations'][0]
    assert all(r['eligible_for_formal_aggregation'] for r in first['criteria'])
    assert d['request_criteria'][0]['outcome']=='SATISFIED'
    pos=dict(first['criteria'][1]['derived'])
    assert pos['separation_deg']*3600==pytest.approx(4.339,abs=.002)
    assert pos['candidate_radius_deg']*3600==pytest.approx(12.131,abs=.002)

@pytest.mark.parametrize('plan,candidate,expected',[(100,130,O.SATISFIED),(130,100,O.SATISFIED),
    (100,130.00000000000003,O.NOT_SATISFIED),(230,240,O.SATISFIED)])
def test_frequency_inclusive_exact_factor(plan,candidate,expected):
    p=payload();p['request']['representative_frequency']['value']=plan
    r,c,_=case(p,frequency=candidate)
    assert evaluate_continuum_frequency(r,c).outcome is expected

def test_representative_frequency_never_averages_or_falls_back():
    p=payload();p['request']['representative_frequency']['value']=100
    r,c,_=case(p)
    assert evaluate_continuum_frequency(r,c).outcome is O.NOT_SATISFIED
    p['request'].pop('representative_frequency');r,c,_=case(p)
    assert evaluate_continuum_frequency(r,c).outcome is None

@pytest.mark.parametrize('candidate,expected',[(.01,O.SATISFIED),(.1,O.SATISFIED),(.2,O.SATISFIED),
    (.20000000000000004,O.NOT_SATISFIED),(None,None),(0,None),(-1,None)])
def test_directional_rms(candidate,expected):
    r,c,_=case(cont_sensitivity_bandwidth=candidate)
    assert evaluate_continuum_rms(r,c).outcome is expected

def test_rms_units_no_angular_scaling_and_no_best_declaration():
    p=payload();p['request']['sensitivities'][0]['rms']={'value':.0001,'unit':'Jy/beam'}
    r,c,_=case(p,spatial_resolution=.05)
    assert evaluate_continuum_rms(r,c).outcome is O.SATISFIED
    duplicate=deepcopy(p['request']['sensitivities'][0]);duplicate['sensitivity_id']='other'
    p['request']['sensitivities'].append(duplicate);r,c,_=case(p)
    assert evaluate_continuum_rms(r,c).outcome is None

@pytest.mark.parametrize('field',['frequency','cont_sensitivity_bandwidth','s_ra'])
def test_missing_metadata_does_not_supply_formal_result(field):
    r,c,e=case()
    source=replace(e.source_record,field_metadata=tuple(replace(f,unit=None) if f.name==field else f
                                                      for f in e.source_record.field_metadata))
    c=build_archive_contexts(source).contexts[0];e=adapt_spatial(c,source)
    result=(evaluate_position_single(r,c,e) if field=='s_ra' else
            evaluate_continuum_frequency(r,c) if field=='frequency' else evaluate_continuum_rms(r,c))
    assert result.outcome is None

@pytest.mark.parametrize('array,diameter',[('12-m',12),('7-m',7),('TP',None),('unknown',None),
    ('A001:DA01 J501:CM01',None),(' '.join(['A001:DA01']*9+['J501:CM01']),None),
    (' '.join(['A001:DA01']*9+['bad']),None)])
def test_unique_diameter_not_majority_label(array,diameter):
    r,c,e=case(array=array);result=evaluate_position_single(r,c,e)
    assert dict(result.derived)['antenna_diameter_m']==diameter
    assert (result.outcome is not None)==(diameter is not None)

@pytest.mark.parametrize('mosaic',['T',None])
def test_mosaic_unknown_not_single_field(mosaic):
    r,c,e=case(mosaic=mosaic)
    assert evaluate_position_single(r,c,e).outcome is None

def test_position_boundary_and_wrap():
    p=payload();p['request']['position'].update(ra=0,dec=0)
    radius=primary_beam_fwhm_deg(240,12)/2
    for offset,expected in [(radius*(1-1e-8),O.SATISFIED),(radius,O.SATISFIED),
                            (radius*(1+1e-8),O.NOT_SATISFIED)]:
        r,c,e=case(p,s_ra=offset,s_dec=0)
        assert evaluate_position_single(r,c,e).outcome is expected
    p['request']['position']['ra']=359.999;r,c,e=case(p,s_ra=.001,s_dec=0)
    result=evaluate_position_single(r,c,e)
    assert result.outcome is O.SATISFIED
    assert dict(result.derived)['separation_deg']==pytest.approx(.002)

@pytest.mark.parametrize('a,b',tuple(itertools.product(T,repeat=2)))
def test_three_value_truth_tables(a,b):
    expected_and=T.FALSE if T.FALSE in (a,b) else T.UNKNOWN if T.UNKNOWN in (a,b) else T.TRUE
    expected_or=T.TRUE if T.TRUE in (a,b) else T.UNKNOWN if T.UNKNOWN in (a,b) else T.FALSE
    assert three_and([a,b]) is expected_and
    assert three_or([a,b]) is expected_or

def replay_report():
    return evaluate_candidate_search(search_candidates(validated(),archive_client=
        RecordedArchiveClient(EXAMPLE/'archive/manifest.json')))

def test_aggregation_gates_unapproved_and_conflicting_evidence():
    report=replay_report();item=report.context_evaluations[0];c=item.candidate.context
    criteria=(*report.request_criteria,*item.criteria)
    unapproved=tuple(replace(r,approval=MethodApproval.PROVISIONAL) if r.criterion_id=='CONT-RMS' else r for r in criteria)
    assert aggregate_continuum(c,unapproved).truth is T.UNKNOWN
    assert aggregate_continuum(replace(c,alternative_context_ids=('another',)),criteria).truth is T.UNKNOWN
    with pytest.raises(ValueError):aggregate_continuum(c,criteria+(criteria[0],))
    with pytest.raises(ValueError):
        aggregate_continuum(c,tuple(replace(r,context_id='another') for r in item.criteria))

@pytest.mark.parametrize('intents,expected',[([],[]),(['LINE'],['LINE']),
    (['CONTINUUM'],['CONTINUUM']),(['CONTINUUM','LINE'],['CONTINUUM','LINE'])])
def test_intents_select_branches(intents,expected):
    p=payload();p['request']['intents']=intents
    report=evaluate_candidate_search(search_candidates(validated(p),archive_client=
        RecordedArchiveClient(EXAMPLE/'archive/manifest.json')))
    assert [b.branch for b in report.context_evaluations[0].branches]==expected
    assert bool(report.request_criteria)==('CONTINUUM' in intents)
    for b in report.context_evaluations[0].branches:
        if b.branch=='LINE':assert b.status=='NOT_IMPLEMENTED' and b.truth is T.UNKNOWN

def test_line_pair_references_reject_cross_spw_and_other_sources():
    from alma_duplicate.domain.line_pairing import LinePairingReference
    report=replay_report();context=report.context_evaluations[0].candidate.context
    request=report.search_result.plan.validation.request
    sensitivity=replace(request.sensitivities[0],purpose='LINE',scope='WINDOW',window_ids=('w0',),
                        basis='SMOOTHED',aggregate_path=None)
    request=replace(request,sensitivities=(sensitivity,))
    pair=LinePairingReference(request.setup_id,'w0',sensitivity.sensitivity_id,context.context_id,
        context.reference.source_record_id,context.evidence.row_link.association_key,
        context.evidence.support_mapping.component_ref)
    window,rms,component=pair.resolve(request,context)
    assert window.window_id=='w0' and rms is sensitivity
    assert component is context.evidence.selected_component
    for bad in [replace(pair,proposed_window_id='w1'),replace(pair,candidate_source_record_id='other'),
                replace(pair,candidate_context_id='other'),replace(pair,proposed_setup_id='other'),
                replace(pair,candidate_component=replace(pair.candidate_component,component_index=99))]:
        with pytest.raises(ValueError):bad.resolve(request,context)


def test_false_and_unknown_is_false_but_does_not_claim_search_absence():
    report=replay_report();item=report.context_evaluations[3]
    criteria=tuple(replace(r,outcome=None,evaluation=E.INSUFFICIENT_INFORMATION)
                   if r.criterion_id=='CONT-RMS' else r for r in item.criteria)
    assert aggregate_continuum(item.candidate.context,(*report.request_criteria,*criteria)).truth is T.FALSE
    assert report.assessment=='NOT_AGGREGATED'

@pytest.mark.parametrize('change',[{'array':'TP'},{'array':'A001:DA01 J501:CM01'},{'mosaic':'T'}])
def test_unsupported_scope_does_not_get_negative_branch_from_other_criteria(change):
    v=validated();source,_=archive(build_search_plan(v),frequency=100,**change)
    report=evaluate_candidate_search(search_candidates(v,archive_result=source))
    assert report.context_evaluations[0].branches[0].status=='INDETERMINATE'


def test_sun_exemption_is_not_a_position_failure():
    r,c,e=case()
    result=evaluate_position_single(replace(r,target_kind='SUN'),c,e)
    assert result.evaluation is E.NOT_APPLICABLE and result.outcome is None
    assert result.reasons==('SOLAR_EXEMPT',)


def test_explicit_conflicting_position_interpretation_blocks_position():
    from alma_duplicate.domain.spatial import PositionInterpretation
    r,c,e=case()
    e=replace(e,interpretation=PositionInterpretation(c.context_id,'ICRS','MOVING','test'))
    result=evaluate_position_single(r,c,e)
    assert result.outcome is None
    assert 'CONFLICTING_POSITION_INTERPRETATION' in result.reasons


def test_nominal_conversion_remains_provisional_and_cannot_make_positive_branch():
    p=payload()
    for w in p['request']['spectral_windows']:
        w['bandwidth_kind']='NOMINAL';w['bandwidth']['value']=1.9
    v=validated(p)
    source=RecordedArchiveClient(EXAMPLE/'archive/manifest.json')
    search=search_candidates(v,archive_client=source)
    report=evaluate_candidate_search(search,nominal_conversion='PORTAL_SCRIPT_V1')
    assert report.request_criteria[0].outcome is O.SATISFIED
    assert report.request_criteria[0].approval is MethodApproval.PROVISIONAL
    assert report.context_evaluations[0].branches[0].truth is T.UNKNOWN


def test_all_required_false_branches_covered_without_short_circuit():
    for key in ['angular','setup','frequency']:
        p=payload()
        if key=='angular':p['request']['angular_resolution']['value']=.1
        elif key=='frequency':p['request']['representative_frequency']['value']=100
        else:
            for w in p['request']['spectral_windows']:w['bandwidth']['value']=1.8
        report=evaluate_candidate_search(search_candidates(validated(p),archive_client=
            RecordedArchiveClient(EXAMPLE/'archive/manifest.json')))
        first=report.context_evaluations[0]
        assert first.branches[0].truth is T.FALSE
        assert len(first.criteria)==4 and first.criteria[-1].outcome is O.SATISFIED
