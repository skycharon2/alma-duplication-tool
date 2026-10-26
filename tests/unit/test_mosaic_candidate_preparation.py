from pathlib import Path
import shutil
from alma_duplicate.mosaic_candidate_preparation import prepare_candidates
from alma_duplicate.clients.archive_products import parse_archive_products

FIXTURE=Path(__file__).parents[1]/'fixtures/archive/mosaic_multi_execution_2026_10_23'
MEMBER='uid://A001/X1284/X28b7'


def discovery(two=False):
    rows=[dict(context_id='good',member_ous_uid=MEMBER,source_name='IC1954')]
    if two:rows.insert(0,dict(context_id='bad',member_ous_uid='uid://A001/X1/X1',source_name='missing'))
    return dict(schema_version='mosaic_candidate_discovery_1',status='COMPLETED',candidates=rows)


def inventory(output,*,member,source):
    if source=='missing':raise ValueError('unavailable inventory')
    output.mkdir()
    for name in ('metadata.xml','inventory_receipt.json'):shutil.copyfile(FIXTURE/name,output/name)
    return dict(status='CAPTURED')


def products(member):
    raw=(FIXTURE/'response.xml').read_bytes()
    return parse_archive_products(raw,member_ous_uid=member),raw,None


def test_failure_isolation_and_automatic_row_selection(tmp_path):
    calls=[]
    def audit(**kw):
        calls.append(kw)
        return dict(executions={'E':{}},unresolved=[],reused_cache=True,completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED')
    r=prepare_candidates(discovery(True),output=tmp_path/'run',cache=tmp_path/'cache',
        inventory_capture=inventory,product_discovery=products,package_audit=audit,offline=True)
    assert [c['status'] for c in r['candidates']]==['FAILED','POINTINGS_PREPARED']
    assert len(calls)==1 and calls[0]['source']=='IC1954'
    assert r['candidates'][1]['reused_cache'] is True
    assert r['status']=='INCOMPLETE'


def test_no_product_does_not_download(tmp_path):
    from dataclasses import replace
    def empty(member):
        result,raw,url=products(member)
        return replace(result,status='EMPTY',products=()),raw,url
    def forbidden(**kwargs):raise AssertionError('Must not download')
    r=prepare_candidates(discovery(),output=tmp_path/'run',cache=tmp_path/'cache',
        inventory_capture=inventory,product_discovery=empty,package_audit=forbidden,offline=True)
    assert r['candidates'][0]['status']=='FAILED'
    assert r['candidates'][0]['stage']=='PRODUCT_DISCOVERY'


def test_ambiguous_products_are_not_chosen(tmp_path,monkeypatch):
    from dataclasses import replace
    import alma_duplicate.mosaic_candidate_preparation as module
    def multiple(member):
        result,raw,url=products(member)
        product=next(p for p in result.products if p.kind=='AUXILIARY_CANDIDATE')
        return replace(result,products=(product,product)),raw,url
    result,_,_=products(MEMBER)
    product=next(p for p in result.products if p.kind=='AUXILIARY_CANDIDATE')
    monkeypatch.setattr(module,'select_auxiliary',lambda *a:(product,'hash',None))
    def forbidden(**kw):raise AssertionError('Ambiguity must not download')
    report=prepare_candidates(discovery(),output=tmp_path/'run',cache=tmp_path/'cache',
        inventory_capture=inventory,product_discovery=multiple,package_audit=forbidden,offline=True)
    assert report['candidates'][0]['status']=='AMBIGUOUS_PRODUCTS'


def test_array_failure_keeps_reconstructed_pointings(tmp_path):
    def audit(**kw):
        return dict(executions={'E':{}},unresolved=[],reused_cache=True,completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED')
    def fail(members):raise ValueError('AQ unavailable')
    r=prepare_candidates(discovery(),output=tmp_path/'run',cache=tmp_path/'cache',
        inventory_capture=inventory,product_discovery=products,package_audit=audit,offline=True,array_fetcher=fail)
    assert r['candidates'][0]['status']=='POINTINGS_PREPARED'
    assert r['candidates'][0]['readiness_status']=='UNAVAILABLE'
    assert r['status']=='INCOMPLETE'


def test_live_catalog_passed_to_readiness(tmp_path,monkeypatch):
    from dataclasses import replace
    from alma_duplicate.archive_array_evidence import load_archive_array_catalog, ArchiveArrayCatalogProvenance, ArchiveArrayCatalogMode
    from alma_duplicate.clients.archive_aq_client import ArchiveAqFetchResult,ArchiveAqMemberQuery
    import alma_duplicate.archive_mosaic_readiness as readiness_module
    captured=load_archive_array_catalog(FIXTURE.parent/'mosaic_array_2026_10_23/manifest.json')
    live=replace(captured,provenance=ArchiveArrayCatalogProvenance(ArchiveArrayCatalogMode.LIVE))
    record=live.records[0]
    fetched=ArchiveAqFetchResult(live,(ArchiveAqMemberQuery(MEMBER,record.url,record.retrieved_at,
        record.response_sha256,len(live.records),100),))
    def audit(**kw):
        return dict(executions={'E':{}},unresolved=[],reused_cache=True,completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED')
    def build(path,*,catalog):
        assert catalog is live
        return dict(executions=[dict(fields=[dict(input_status='NOT_READY', position_status='EVIDENCE_BOUND')])])
    monkeypatch.setattr(readiness_module,'build_readiness',build)
    r=prepare_candidates(discovery(),output=tmp_path/'run',cache=tmp_path/'cache',
        inventory_capture=inventory,product_discovery=products,package_audit=audit,offline=True,
        array_fetcher=lambda members:fetched)
    assert r['candidates'][0]['readiness_status']=='EVIDENCE_BOUND'
    assert r['status']=='COMPLETED'


def test_explicit_resource_limits_reach_audit_and_receipt(tmp_path):
    from alma_duplicate.mosaic_resource_limits import MosaicResourceLimits
    from dataclasses import asdict
    limits = MosaicResourceLimits(1_000_000_000, 1_000_000_000, 10_000_000_000)
    def audit(**kwargs):
        assert {k: kwargs[k] for k in asdict(limits)} == asdict(limits)
        raise ValueError('simulated inspection budget exceeded')
    report = prepare_candidates(discovery(), output=tmp_path/'run', cache=tmp_path/'cache',
        inventory_capture=inventory, product_discovery=products, package_audit=audit,
        offline=True, resource_limits=limits)
    assert report['resource_limits'] == asdict(limits)
    assert report['candidates'][0]['status'] == 'FAILED'
    assert 'budget exceeded' in report['candidates'][0]['error']


def test_missing_inventory_execution_is_partial(tmp_path):
    def audit(**kw):
        return dict(executions={'E': {}}, unresolved=[], reused_cache=True,
            missing_tap_asdm_uids=['missing'], completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED',
            inspection={'alternative_evidence': [{'position_status': 'NOT_READY'}]})
    report = prepare_candidates(discovery(), output=tmp_path/'run', cache=tmp_path/'cache',
        inventory_capture=inventory, product_discovery=products, package_audit=audit, offline=True)
    candidate = report['candidates'][0]
    assert candidate['status'] == 'PARTIAL_EVIDENCE'
    assert candidate['missing_tap_asdm_uids'] == ['missing']
    assert candidate['alternative_pointing_evidence'][0]['position_status'] == 'NOT_READY'
