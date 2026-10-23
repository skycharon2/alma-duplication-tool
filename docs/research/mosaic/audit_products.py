"""Opt-in metadata-only reproduction for the fixed public examples.
No product links are followed. Output directory must be supplied explicitly.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup
from alma_duplicate.clients.archive_aq_client import ArchiveAqClient

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
uid = 'uid://A001/X3733/X169'
try:
    result = ArchiveAqClient(max_hits=20).fetch_members([uid])
    (out/'aq_example.json').write_text(json.dumps(asdict(result), indent=2, default=str)+'\n')
except Exception as exc:
    (out/'aq_error.json').write_text(json.dumps({'member': uid, 'error_type': type(exc).__name__, 'state': 'UNAVAILABLE_EVIDENCE'})+'\n')

for name, url, params in (
    ('datalink', 'https://almascience.eso.org/datalink/sync', {'ID': uid}),
    ('published_product', 'https://casaguides.nrao.edu/index.php/AntennaeBand7_Calibration_6.4', {}),
):
    record = {'url': url, 'parameters': params, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
    try:
        with requests.get(url, params=params, timeout=(10,45), stream=True) as response:
            record['http_status'] = response.status_code
            response.raise_for_status()
            raw = b''
            for chunk in response.iter_content(65536):
                raw += chunk
                if len(raw) > 2_000_000:
                    raise ValueError('Metadata response exceeds 2 MB cap')
        record.update(bytes=len(raw), sha256=sha256(raw).hexdigest())
        if name == 'datalink':
            (out/'datalink.xml').write_bytes(raw)
        else:
            text = BeautifulSoup(raw, 'html.parser').get_text('\n', strip=True)
            rows = []
            for line in text.splitlines():
                match = re.match(r'\s*(\d+)\s+none\s+NGC4038 - Antennae\s+\*?(\S+)\s+(\S+)\s+J2000\s+(\d+)\s+(\d+)', line)
                if match:
                    fid, ra, dec, source, count = match.groups()
                    rows.append(dict(field_id=int(fid), ra_hms=ra, dec_dms=dec,
                                     frame='J2000', source_id=int(source), nrows=int(count)))
            (out/'published_pointing_rows.json').write_text(json.dumps({
                'url': url, 'asdm_uid': 'uid://A002/X1ff7b0/Xb',
                'ms_basename': 'uid___A002_X1ff7b0_Xb.ms',
                'status': 'PUBLISHED_TABLE_ONLY_NOT_PRODUCT_VALIDATED',
                'rows': rows}, indent=2)+'\n')
    except Exception as exc:
        record.update(error_type=type(exc).__name__, state='UNAVAILABLE_EVIDENCE')
    (out/(name+'_provenance.json')).write_text(json.dumps(record, indent=2)+'\n')
