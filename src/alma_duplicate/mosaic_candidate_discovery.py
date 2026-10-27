"""Bounded Archive region searches across every supplied proposed pointing."""
from datetime import datetime, timezone
from hashlib import sha256
from http.client import HTTPException
import json
import math
from pathlib import Path
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS, validate_origins
from alma_duplicate.archive_mosaic_discovery import _fetch, MAX_ROWS
from alma_duplicate.archive_mosaic_pipeline import read_candidate_rows, MAX_METADATA_BYTES


def plan_discovery(proposed, *, margin_arcsec, origin=ARCHIVE_ORIGINS[0]):
    if origin not in ARCHIVE_ORIGINS:
        raise ValueError('Official Archive origin required')
    if isinstance(margin_arcsec,bool) or not math.isfinite(margin_arcsec) or not 0 <= margin_arcsec <= 3600:
        raise ValueError('Explicit search margin must be between 0 and 3600 arcsec')
    positions = {}
    for p in proposed['points']:
        ra,dec=p['ra_deg'],p['dec_deg']
        if p.get('frame')!='ICRS' or not math.isfinite(ra) or not math.isfinite(dec) or not 0<=ra<360 or not -90<=dec<=90:
            raise ValueError('Valid ICRS proposed coordinates required')
        positions.setdefault((ra,dec),[]).append(p['id'])
    if not 1 <= len(positions) <= 2000:
        raise ValueError('Discovery supports 1 to 2000 unique positions per run')
    coordinates=list(positions)
    requests=[]
    for start in range(0,len(coordinates),20):
        subset=coordinates[start:start+20]
        predicates=[]
        for ra,dec in subset:
            if margin_arcsec == 0:
                predicates.append(f"1=CONTAINS(POINT('ICRS',{ra:.17g},{dec:.17g}),s_region)")
            else:
                predicates.append(f"1=INTERSECTS(CIRCLE('ICRS',{ra:.17g},{dec:.17g},{margin_arcsec/3600:.17g}),s_region)")
        query=("SELECT DISTINCT proposal_id,member_ous_uid,asdm_uid,target_name,science_observation,is_mosaic "
               "FROM ivoa.obscore WHERE science_observation='T' AND ("
               + ' OR '.join(predicates)+')')
        params=dict(REQUEST='doQuery',LANG='ADQL',FORMAT='votable',MAXREC=str(MAX_ROWS),QUERY=query)
        requests.append(dict(query=query,url=origin+'/tap/sync?'+urlencode(params),
            kind='REGION', proposed_ids=[pid for coord in subset for pid in positions[coord]],maxrec=MAX_ROWS))
    query=("SELECT DISTINCT proposal_id,member_ous_uid,asdm_uid,target_name,science_observation,is_mosaic "
           "FROM ivoa.obscore WHERE science_observation='T' AND s_region IS NULL")
    params=dict(REQUEST='doQuery',LANG='ADQL',FORMAT='votable',MAXREC=str(MAX_ROWS),QUERY=query)
    requests.append(dict(query=query,url=origin+'/tap/sync?'+urlencode(params),
                         kind='NULL_REGION_FALLBACK',proposed_ids=[],maxrec=MAX_ROWS))
    return dict(schema_version='mosaic_candidate_discovery_plan_1',origin=origin,
        proposed_sha256=proposed['input_sha256'],margin_arcsec=margin_arcsec,requests=requests,
        scope='PUBLIC_SCIENCE_ALL_GEOMETRIES_REGION_PREFILTER_WITH_NULL_REGION_FALLBACK',
        recall_status='NOT_ESTABLISHED_FOR_RECONSTRUCTED_HALF_POWER_COVERAGE')


def discover_candidates(proposed, output: Path, *, margin_arcsec, origin=ARCHIVE_ORIGINS[0], fetch=None, origins=None):
    if origins is not None:
        origins = validate_origins(origins)
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        attempts = []
        selected = None
        selected_directory = None
        for index, mirror in enumerate(origins):
            directory = f'mirror-{index:02d}'
            report = discover_candidates(proposed, output / directory,
                margin_arcsec=margin_arcsec, origin=mirror, fetch=fetch)
            attempts.append(dict(origin=mirror, status=report['status'],
                candidate_count=report['candidate_count'], report_file=f'{directory}/discovery.json'))
            # Preserve the most informative partial attempt if no mirror completes.
            # Never combine candidates or completeness evidence across mirrors.
            if selected is None or report['status'] == 'COMPLETED' or report['candidate_count'] > selected['candidate_count']:
                selected, selected_directory = report, directory
            if report['status'] == 'COMPLETED':
                break
        selected['mirror_attempts'] = attempts
        for receipt in selected['requests']:
            if 'response_file' in receipt:
                receipt['response_file'] = f"{selected_directory}/{receipt['response_file']}"
        (output / 'discovery.json').write_text(json.dumps(selected, indent=2, allow_nan=False) + '\n')
        (output / 'candidates.json').write_bytes((output / selected_directory / 'candidates.json').read_bytes())
        return selected
    plan=plan_discovery(proposed,margin_arcsec=margin_arcsec,origin=origin)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    groups, receipts = {}, []
    for index, request in enumerate(plan['requests']):
        receipt=dict(request_index=index,status='FAILED',started_at=datetime.now(timezone.utc).isoformat())
        try:
            code,raw=(fetch or _fetch)(request['url'])
            raw=raw[:MAX_METADATA_BYTES+1]
            filename=f'response-{index:04d}.xml';(output/filename).write_bytes(raw)
            receipt.update(http_status=code,response_file=filename,response_sha256=sha256(raw).hexdigest(),response_bytes=len(raw))
            if code!=200:
                raise ValueError(f'HTTP {code}')
            rows=read_candidate_rows(raw)
            if len(rows)>=MAX_ROWS:
                raise ValueError('MAXREC reached; query completeness unknown')
            receipt.update(status='COMPLETED',row_count=len(rows))
            for row in rows:
                key=(row['proposal_id'],row['member_ous_uid'],row['target_name'])
                group=groups.setdefault(key,dict(project_code=key[0],member_ous_uid=key[1],source_name=key[2],
                    asdm_uids=set(),request_indices=set(),geometry_flags=set()))
                group['geometry_flags'].add(row['is_mosaic']);group['asdm_uids'].add(row['asdm_uid']);group['request_indices'].add(index)
        except (OSError,HTTPException,ValueError,ET.ParseError) as exc:
            receipt['error']=str(exc)
        receipts.append(receipt)
    candidates=[]
    for key,g in sorted(groups.items()):
        g['geometry_flags']=sorted(g['geometry_flags']);g['asdm_uids']=sorted(g['asdm_uids']);g['request_indices']=sorted(g['request_indices'])
        g['context_id']='ARCHIVE:MOSAIC:'+sha256(json.dumps(key).encode()).hexdigest()
        g['coverage_status']='NOT_RECONSTRUCTED'
        candidates.append(g)
    report=dict(schema_version='mosaic_candidate_discovery_1',plan=plan,requests=receipts,candidates=candidates,
        status='COMPLETED' if all(r['status']=='COMPLETED' for r in receipts) else 'INCOMPLETE',
        candidate_count=len(candidates),policy_status='NOT_EVALUATED',
        absence_interpretation='NO_DUPLICATION_CONCLUSION_FROM_EMPTY_SEARCH')
    (output/'discovery.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    manifest=dict(schema_version='mosaic_candidates_1',candidates=[{k:c[k] for k in
        ('context_id','member_ous_uid','source_name')} for c in candidates])
    (output/'candidates.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return report
