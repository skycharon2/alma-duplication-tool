"""Bounded public metadata probe; no science data/product downloads.
Writes only to the explicit evidence output directory. No runtime edits.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import requests
from astropy.io.votable import parse_single_table

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
endpoint = 'https://almascience.eso.org/tap/sync'
columns = 'proposal_id,member_ous_uid,asdm_uid,target_name,s_ra,s_dec,s_region,s_fov,is_mosaic,frequency,antenna_arrays,obs_publisher_did'
queries = {
 'tap_schema': "SELECT column_name,datatype,unit,description FROM TAP_SCHEMA.columns WHERE table_name='ivoa.obscore'",
 'tap_examples': f"SELECT TOP 2 {columns} FROM ivoa.obscore WHERE is_mosaic='T' AND science_observation='T' AND data_rights='Public'",
}
records = []
for name, query in queries.items():
    params = {'REQUEST':'doQuery','LANG':'ADQL','FORMAT':'votable','MAXREC':200,'QUERY':query}
    record = {'name':name,'endpoint':endpoint,'parameters':params,'started_at':datetime.now(timezone.utc).isoformat()}
    try:
        with requests.get(endpoint, params=params, timeout=(10,45), stream=True) as response:
            record['http_status'] = response.status_code
            response.raise_for_status()
            raw = b''
            for part in response.iter_content(65536):
                raw += part
                if len(raw) > 2_000_000:
                    raise ValueError('Metadata response exceeds 2 MB cap')
        table = parse_single_table(BytesIO(raw)).to_table()
        (out / (name + '.xml')).write_bytes(raw)
        rows = [{k: (None if getattr(row[k], 'mask', False) else str(row[k])) for k in table.colnames} for row in table]
        record.update(bytes=len(raw), sha256=sha256(raw).hexdigest(),rows=rows,
                      scope='TOP 2 sample only; not catalogue-complete' if name=='tap_examples' else 'obscore column metadata; inspect QUERY_STATUS')
    except Exception as exc:
        record.update(error_type=type(exc).__name__,state='UNAVAILABLE_EVIDENCE')
    records.append(record)
    (out/'archive_probe.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps([{k:v for k,v in r.items() if k not in ('rows','parameters')} for r in records],indent=2))
