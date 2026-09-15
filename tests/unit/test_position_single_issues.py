from dataclasses import replace
import pytest
from alma_duplicate.rules.position_single import evaluate_position_single
from tests.integration.test_queue_candidate_beam import search
from tests.integration.test_position_single import criterion


@pytest.mark.parametrize('change,side,path',[
    ({'Use 7-m?':'True'},'CANDIDATE','context.request.use_7m/use_tp'),
    ({'Mosaic':'Custom'},'METHOD','context.spatial.selection_status'),
    ({'RA':'0','Dec':'0'},'CANDIDATE','context.spatial.center'),
])
def test_candidate_and_method_issues(change,side,path):
    r=criterion(search(change))
    assert r.outcome is None
    assert any(i.side==side and i.path==path for i in r.issues)


def test_boundary_method_issue():
    r=criterion(search(dec=20+8.601107285572768/3600))
    assert r.issues[0].side=='METHOD'
    assert r.issues[0].code=='SPATIAL_BOUNDARY_TOLERANCE'


def test_request_issue():
    s=search();row=s.queue.rows[0]
    r=evaluate_position_single(replace(s.plan.validation.request,position=None),row.context,row.spatial_evidence)
    assert r.issues[0].side=='PROPOSED'
    assert r.issues[0].path=='request.position'


def test_success_has_no_missing_issues():
    r=criterion(search())
    assert r.outcome=='SATISFIED' and not r.issues
