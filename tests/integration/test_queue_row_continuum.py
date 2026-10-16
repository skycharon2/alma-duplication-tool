"""One coherent row supplies common criteria to both observing intents."""
from dataclasses import replace
from itertools import product
import pytest
from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from tests.integration.test_queue_continuum import case, rule
from tests.integration.test_queue_row_beam import source, ABSENT
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from tests.integration.test_confirmed_continuum import payload, validated


@pytest.mark.parametrize('use7,tp', list(product(('True','False'),repeat=2)))
@pytest.mark.parametrize('frequency,status',[(230,'CRITERIA_MET'),(400,'CRITERIA_NOT_MET')])
def test_auxiliary_flags_do_not_gate_continuum(use7,tp,frequency,status):
    _,_,c=case({'Use 7-m?':use7,'Use TP?':tp},frequency=frequency)
    assert c.branches[0].status==status
    for evaluated in ([v.evaluation for v in c.beam_variants] or [c]):
        assert rule(evaluated,'ANGULAR').outcome=='SATISFIED'
        assert rule(evaluated,'CONT-RMS').outcome=='SATISFIED'


def test_position_false_and_missing_rms_is_false_with_auxiliary_flags():
    s,_,_=case({'Use 7-m?':'True','Use TP?':'True','Dec':'-43.01'})
    req=replace(s.plan.validation.request,sensitivities=())
    s=replace(s,plan=replace(s.plan,validation=replace(s.plan.validation,request=req)))
    c=evaluate_candidate_search(s,queue_continuum=True).context_evaluations[0]
    assert len(c.beam_variants) == 2
    for v in c.beam_variants:
        assert rule(v.evaluation,'POS-SINGLE').outcome=='NOT_SATISFIED'
        assert rule(v.evaluation,'CONT-RMS').outcome is None
    assert c.branches[0].status=='CRITERIA_NOT_MET'


@pytest.mark.parametrize('standalone',[ABSENT,'True','False'])
@pytest.mark.parametrize('intents',[['LINE'],['CONTINUUM','LINE']])
def test_line_receives_identical_common_position(standalone,intents):
    p=payload();p['request']['position'].update(ra=10,dec=20)
    p['request']['intents']=intents;p['search_options']['sources']=['QUEUE']
    q=parse_queue_csv_bytes(source(standalone, use7='True' if standalone == 'True' else 'False'))
    search=search_candidates(validated(p),queue_result=q)
    c=evaluate_candidate_search(search,queue_continuum=True).context_evaluations[0]
    pos=rule(c,'POS-SINGLE')
    assert pos.outcome=='SATISFIED'
    assert dict(pos.derived)['antenna_diameter_m']==(7 if standalone=='True' else 12)
    assert c.line_pairs
    for pair in c.line_pairs:
        assert next(r for r in pair.criteria if r.criterion_id=='POS-SINGLE') is pos
    # Queue line numerical rules are separate unfinished work, not a position gate.
    assert next(b for b in c.branches if b.branch=='LINE').status=='INDETERMINATE'


@pytest.mark.parametrize("tp", ["True", "False"])
@pytest.mark.parametrize("intents", [["LINE"], ["CONTINUUM", "LINE"]])
@pytest.mark.parametrize("standalone", ["True", "False"])
def test_standalone_conflict_gates_formal_queue_branches(tp, intents, standalone):
    p = payload()
    p["request"]["position"].update(ra=10, dec=20)
    p["request"]["intents"] = intents
    p["search_options"]["sources"] = ["QUEUE"]
    raw = source(standalone, use7="False", tp=tp)
    q = parse_queue_csv_bytes(raw)
    search = search_candidates(validated(p), queue_result=q)
    c = evaluate_candidate_search(
        search, queue_continuum="CONTINUUM" in intents, queue_line=True,
    ).context_evaluations[0]
    line = next(b for b in c.branches if b.branch == "LINE")
    assert line.method_version == "queue_line_context_or_1"
    assert {b.branch for b in c.branches} == set(intents)
    assert not c.beam_variants
    assert c.line_pairs
    pos = rule(c, "POS-SINGLE")
    for pair in c.line_pairs:
        assert pair.method_version == "queue_line_pair_and_1"
        assert next(r for r in pair.criteria if r.criterion_id == "POS-SINGLE") is pos
        # This fixture has a genuine spectral coverage failure. The conflict
        # gate must override it, not accidentally turn UNKNOWN into FALSE.
        assert next(r for r in pair.criteria if r.criterion_id == "LINE-COVERAGE").outcome == "NOT_SATISFIED"

    if standalone == "True":
        assert pos.outcome is None
        assert "STANDALONE_WITHOUT_7M_REQUEST" in pos.reasons
        assert dict(pos.details)["common_scope"] == "UNRESOLVED"
        assert all(b.status == "INDETERMINATE" and b.truth == "UNKNOWN" for b in c.branches)
        assert "BRANCH_SCOPE_UNSUPPORTED" in line.reasons
        assert all(pair.truth == "UNKNOWN" and "BRANCH_SCOPE_UNSUPPORTED" in pair.reasons
                   for pair in c.line_pairs)
    else:
        # Changing only the conflicting field restores a valid D12 path. This
        # control prevents an unconditional UNKNOWN implementation from passing.
        assert pos.outcome == "SATISFIED"
        assert dict(pos.derived)["antenna_diameter_m"] == 12.0
        assert dict(pos.details)["common_scope"] == "SUPPORTED"
        assert "STANDALONE_WITHOUT_7M_REQUEST" not in pos.reasons
        assert line.status == "CRITERIA_NOT_MET" and line.truth == "FALSE"
        assert "BRANCH_SCOPE_UNSUPPORTED" not in line.reasons
        assert all(pair.truth == "FALSE" for pair in c.line_pairs)
    assert c.candidate.context.evidence.row.raw_row.value("standAlone_ACA") == standalone
