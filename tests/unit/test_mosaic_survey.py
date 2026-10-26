from experiments.mosaic_acquisition_survey.run import select_diverse,sample_rows
import pytest


def test_project_diversity_and_identity_deduplication():
    rows=[dict(proposal_id=p,member_ous_uid=m,target_name='T') for p,m in
          [('A','1'),('A','2'),('B','3'),('C','4'),('C','4')]]
    seen=set();r=select_diverse(rows,seen,count=3)
    assert [x['member_ous_uid'] for x in r]==['1','3','4']
    assert [x['member_ous_uid'] for x in select_diverse(rows,seen,count=3)]==['2']


def test_overflow_cannot_be_used_as_successful_sample():
    raw=b'<VOTABLE xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE><INFO name="QUERY_STATUS" value="OVERFLOW"/></RESOURCE></VOTABLE>'
    with pytest.raises(ValueError,match='truncated'):sample_rows(raw)
