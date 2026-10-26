"""Automatically acquire and reconstruct pointings for discovered Archive candidates."""
from dataclasses import asdict
from alma_duplicate.mosaic_resource_limits import MosaicResourceLimits
from hashlib import sha256
from http.client import HTTPException
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.archive_mosaic_discovery import capture_inventory, verify_inventory_capture
from alma_duplicate.archive_mosaic_pipeline import read_mosaic_rows
from alma_duplicate.clients.archive_products import discover_archive_products
from alma_duplicate.archive_auxiliary import select_auxiliary
from alma_duplicate.archive_mosaic_package_audit import audit_package


def acquire_candidate_array(directory, member, *, offline, array_fetcher):
    from alma_duplicate.clients.archive_aq_client import ArchiveAqClient
    from alma_duplicate.archive_array_acquisition import _check_result
    if offline and array_fetcher is None:
        return None
    fetched = (array_fetcher or ArchiveAqClient().fetch_members)((member,))
    _check_result(fetched, (member,))
    (directory/'array_acquisition.json').write_text(json.dumps(dict(
        queries=[asdict(q) for q in fetched.queries],
        records=[asdict(r) for r in fetched.catalog.records],
        provenance=asdict(fetched.catalog.provenance),
        properties_url=fetched.properties_url), indent=2)+'\n')
    return fetched.catalog


def prepare_candidate_chunk(discovery, *, output, cache, inventory_capture=None, product_discovery=None,
                       package_audit=None, offline=False, array_fetcher=None, resource_limits=None):
    """Prepare each distinct Member/target; isolate failures without negative verdicts.

    Injectable acquisition functions support replay of captured metadata. Offline
    production reuse is handled by the verified auxiliary cache, not fabricated TAP
    receipts. A fresh run directory preserves every acquisition attempt.
    """
    limits = resource_limits or MosaicResourceLimits()
    if not isinstance(limits, MosaicResourceLimits):
        raise ValueError('Expected MosaicResourceLimits')
    if discovery.get('schema_version') != 'mosaic_candidate_discovery_1':
        raise ValueError('Expected Mosaic candidate discovery report')
    rows=discovery['candidates']
    if not isinstance(rows,list) or len(rows)>100:
        raise ValueError('At most 100 candidates per preparation run')
    seen=set()
    for row in rows:
        key=(row['member_ous_uid'],row['source_name'])
        if any(not isinstance(v,str) or not v.strip() for v in key) or key in seen:
            raise ValueError('Invalid or duplicate Member/target identity')
        seen.add(key)
    if offline and any('T' in r.get('geometry_flags', ['T']) for r in rows) and (inventory_capture is None or product_discovery is None):
        raise ValueError('Offline preparation requires explicit metadata replay providers')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    results=[]
    for row in rows:
        member,source=row['member_ous_uid'],row['source_name']
        directory=output/sha256(json.dumps([member,source]).encode()).hexdigest()
        directory.mkdir()
        result=dict(context_id=row['context_id'],member_ous_uid=member,source_name=source,
            directory=str(directory),status='FAILED',stage='INVENTORY',policy_status='NOT_EVALUATED')
        try:
            flags = row.get('geometry_flags', ['T'])
            result['geometry_flags'] = flags
            if 'T' not in flags:
                result['stage'] = 'ARRAY_READINESS'
                catalog = acquire_candidate_array(directory, member, offline=offline, array_fetcher=array_fetcher)
                result.update(status='METADATA_ONLY_PREPARED',
                    readiness_status='ARRAY_ACQUIRED' if catalog is not None else 'ARRAY_ACQUISITION_NOT_REQUESTED_OFFLINE',
                    pointing_source='ARCHIVE_CONTEXT_CENTER_IF_SINGLE')
                results.append(result)
                (directory/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
                continue
            inventory=(inventory_capture or capture_inventory)(directory/'inventory',member=member,source=source)
            if inventory['status']!='CAPTURED':
                raise ValueError('Inventory unavailable: '+inventory['status'])
            metadata=(directory/'inventory/metadata.xml').read_bytes()
            verify_inventory_capture(metadata,directory/'inventory/inventory_receipt.json',member=member,source=source)
            if row.get('project_code') is not None and any(r['proposal_id']!=row['project_code'] for r in read_mosaic_rows(metadata)):
                raise ValueError('Discovered project differs from inventory')
            result['stage']='PRODUCT_DISCOVERY'
            products,raw,url=(product_discovery or discover_archive_products)(member)
            product_dir=directory/'products';product_dir.mkdir()
            receipt=dict(schema_version='archive_product_discovery_1',mode='OFFLINE_REPLAY' if offline else 'LIVE_METADATA',
                request_url=url,response_file='response.xml' if raw is not None else None,
                capture_truncated=False,discovery=asdict(products))
            if raw is not None:(product_dir/'response.xml').write_bytes(raw)
            receipt_path=product_dir/'discovery.json'
            receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
            if products.member_ous_uid!=member or products.status not in ('DISCOVERED','DISCOVERED_WITH_ISSUES'):
                raise ValueError('Product discovery unavailable or Member mismatch')
            result['stage']='PRODUCT_SELECTION'
            eligible=[];rejected=[]
            for index,product in enumerate(products.products):
                if product.kind!='AUXILIARY_CANDIDATE':continue
                try:
                    verified,_,_=select_auxiliary(receipt_path,index)
                    if verified.member_ous_uid!=member:raise ValueError('Product Member mismatch')
                    eligible.append(index)
                except (ValueError,OSError) as exc:
                    rejected.append(dict(row_index=index,reason=str(exc)))
            result.update(eligible_product_rows=eligible,rejected_product_rows=rejected)
            if len(eligible)!=1:
                result['status']='AMBIGUOUS_PRODUCTS' if eligible else 'NO_USABLE_AUXILIARY_PRODUCT'
            else:
                result['stage']='PACKAGE_RECONSTRUCTION'
                audit=(package_audit or audit_package)(metadata=directory/'inventory/metadata.xml',
                    capture_receipt=directory/'inventory/inventory_receipt.json',receipt=receipt_path,
                    row_index=eligible[0],cache=Path(cache),output=directory/'package',member=member,
                    source=source,offline=offline,
                    **(asdict(limits) if resource_limits is not None else {}))
                result.update(package_audit_dir=str(directory/'package'),
                    execution_count=len(audit['executions']),unresolved=audit['unresolved'],
                    missing_tap_asdm_uids=audit.get('missing_tap_asdm_uids', []),
                    alternative_pointing_evidence=audit.get('inspection', {}).get('alternative_evidence', []),
                    reused_cache=audit['reused_cache'],completeness=audit['completeness'],
                    status='POINTINGS_PREPARED' if audit['executions'] and not audit['unresolved'] and not audit.get('missing_tap_asdm_uids') else 'PARTIAL_EVIDENCE')
                if audit['executions']:
                    from alma_duplicate.archive_mosaic_readiness import build_readiness
                    from alma_duplicate.clients.archive_aq_client import ArchiveAqClient
                    from alma_duplicate.archive_array_acquisition import _check_result
                    result['stage']='ARRAY_READINESS'
                    if offline and array_fetcher is None:
                        result['readiness_status']='ARRAY_ACQUISITION_NOT_REQUESTED_OFFLINE'
                    else:
                        fetched=(array_fetcher or ArchiveAqClient().fetch_members)((member,))
                        _check_result(fetched,(member,))
                        (directory/'array_acquisition.json').write_text(json.dumps(dict(
                            queries=[asdict(q) for q in fetched.queries],
                            records=[asdict(r) for r in fetched.catalog.records],
                            provenance=asdict(fetched.catalog.provenance),
                            properties_url=fetched.properties_url),indent=2)+'\n')
                        readiness=build_readiness(directory/'package',catalog=fetched.catalog)
                        (directory/'readiness.json').write_text(json.dumps(readiness,indent=2)+'\n')
                        result['readiness_file']=str(directory/'readiness.json')
                        result['readiness_status']=('EVIDENCE_BOUND' if readiness['executions'] and all(
                            e['fields'] and all(f['position_status']=='EVIDENCE_BOUND' for f in e['fields'])
                            for e in readiness['executions']) else 'NOT_READY')
        except (OSError,ValueError,KeyError,TypeError,HTTPException,ET.ParseError) as exc:
            result['error']=str(exc)
            if result['stage']=='ARRAY_READINESS':
                result['readiness_status']='UNAVAILABLE'
            else:
                result['status']='FAILED'
        if {'F', 'T'}.issubset(result.get('geometry_flags', ())) and not (directory/'array_acquisition.json').exists():
            try:
                catalog = acquire_candidate_array(directory, member, offline=offline, array_fetcher=array_fetcher)
                result['single_field_array_status'] = 'ARRAY_ACQUIRED' if catalog is not None else 'UNAVAILABLE'
            except (OSError, ValueError, KeyError, TypeError, HTTPException) as exc:
                result['single_field_array_status'] = 'UNAVAILABLE'
                result['single_field_array_error'] = str(exc)
        results.append(result)
        (directory/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    report=dict(schema_version='mosaic_candidate_preparation_1',candidates=results,
        resource_limits=asdict(limits),
        discovery_status=discovery.get('status'),discovery_scope=discovery.get('plan',{}).get('scope'),
        status='COMPLETED' if all(((r['status']=='POINTINGS_PREPARED' and r.get('readiness_status')=='EVIDENCE_BOUND') or (r['status']=='METADATA_ONLY_PREPARED' and r.get('readiness_status')=='ARRAY_ACQUIRED')) for r in results) else 'INCOMPLETE',
        discovery_recall_status=discovery.get('plan',{}).get('recall_status'),
        scope='POINTING_AND_ARRAY_READINESS_NOT_SPECTRAL_SELECTION',policy_status='NOT_EVALUATED')
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def prepare_candidates(discovery, *, output, cache, max_candidates=100, resume=False, **kwargs):
    """Process a bounded prefix and retain every pending identity for later resume."""
    from alma_duplicate.mosaic_preparation_batches import prepare_batches
    return prepare_batches(discovery, output=output, cache=cache,
                           max_candidates=max_candidates, resume=resume,
                           worker=prepare_candidate_chunk, worker_kwargs=kwargs)
