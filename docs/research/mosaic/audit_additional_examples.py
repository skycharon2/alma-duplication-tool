"""Two additional public mosaics from distinct projects; metadata only.
Run from repository root with --out /tmp/mosaic-additional-recheck.
Never follows observing-product links or writes to the Queue store.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import requests
from astropy.io.votable import parse_single_table
from alma_duplicate.clients.archive_aq_client import ArchiveAqClient

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--labels', nargs='+', default=['C', 'D'])
ap.add_argument('--exclude-project', action='append', default=[])
ap.add_argument('--non-solar', action='store_true')
ap.add_argument('--manifest', default='additional_examples.json')
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
records = []

def fetch(name, url, params):
    record = dict(name=name, url=url, parameters=params,
                  retrieved_at=datetime.now(timezone.utc).isoformat())
    records.append(record)
    with requests.get(url, params=params, timeout=(10,45), stream=True) as response:
        record['http_status'] = response.status_code
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_content(65536):
            raw.extend(chunk)
            if len(raw) > 2_000_000:
                raise ValueError('Metadata exceeds 2 MB cap')
    raw = bytes(raw)
    record.update(bytes=len(raw), sha256=sha256(raw).hexdigest())
    (out/(name+'.xml')).write_bytes(raw)
    statuses = [n.attrib.get('value') for n in ET.fromstring(raw).iter()
                if n.tag.rsplit('}',1)[-1]=='INFO' and n.attrib.get('name')=='QUERY_STATUS']
    record['query_status'] = statuses
    if any(s != 'OK' for s in statuses):
        raise ValueError('Non-OK query status')
    table = parse_single_table(BytesIO(raw)).to_table()
    record['rows'] = [{k: None if getattr(row[k], 'mask', False) else str(row[k])
                       for k in table.colnames} for row in table]
    return record

excluded = ['2023.1.00687.S'] + a.exclude_project
columns = ('proposal_id,member_ous_uid,asdm_uid,obs_id,target_name,s_ra,s_dec,'
           's_region,s_fov,is_mosaic,frequency,antenna_arrays,obs_publisher_did,'
           'data_rights,science_observation,obs_release_date')
try:
    for label in a.labels:
        query = (f'SELECT TOP 1 {columns} FROM ivoa.obscore '
                 "WHERE is_mosaic='T' AND science_observation='T' AND data_rights='Public' "
                 + ("AND target_name <> 'Sun' " if a.non_solar else '')
                 + ''.join("AND proposal_id <> '"+p.replace("'","''")+"' " for p in excluded))
        tap = fetch('case_'+label+'_tap', 'https://almascience.eso.org/tap/sync',
                    dict(REQUEST='doQuery',LANG='ADQL',FORMAT='votable',MAXREC=1,QUERY=query))
        assert len(tap['rows']) == 1 and tap['query_status']==['OK']
        row = tap['rows'][0]
        excluded.append(row['proposal_id'])
        member = row['member_ous_uid']
        tap['scope'] = 'One public science mosaic row; not a complete Member or catalogue query'
        try:
            aq = ArchiveAqClient(max_hits=100).fetch_members([member])
            data = asdict(aq)
            (out/('case_'+label+'_aq.json')).write_text(json.dumps(data,indent=2,default=str)+'\n')
            tap['aq_exact_source_hits'] = [asdict(r) for r in aq.catalog.records if r.source_name==row['target_name']]
            tap['aq_total_hits'] = len(aq.catalog.records)
        except Exception as exc:
            tap['aq_error'] = dict(type=type(exc).__name__,code=getattr(exc,'code',None))
        dl = fetch('case_'+label+'_datalink', 'https://almascience.eso.org/datalink/sync', {'ID':member})
        dl['semantics_counts'] = dict(Counter(r['semantics'] for r in dl['rows']))
        dl['scope'] = 'Product discovery only; no product links or service descriptors followed'
        print(label, row['proposal_id'], member, row['asdm_uid'], row['target_name'],
              'AQ hits',tap.get('aq_total_hits'), 'DataLink rows',len(dl['rows']),flush=True)
except Exception as exc:
    records.append(dict(state='UNAVAILABLE_EVIDENCE',error_type=type(exc).__name__))
    raise
finally:
    (out/a.manifest).write_text(json.dumps(records,indent=2)+'\n')
