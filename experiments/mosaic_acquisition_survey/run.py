"""Bounded public Mosaic product preflight; no auxiliary downloads."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from alma_duplicate.archive_mosaic_discovery import _fetch
from alma_duplicate.clients.archive_products import discover_archive_products

NS='{http://www.ivoa.net/xml/VOTable/v1.3}'


def sample_rows(raw):
    root=ET.fromstring(raw)
    statuses=[i.get('value') for i in root.iter(NS+'INFO') if i.get('name')=='QUERY_STATUS']
    if not statuses or any(s!='OK' for s in statuses):raise ValueError('Unsuccessful or truncated TAP response')
    table=root.find('.//'+NS+'TABLE')
    names=[f.get('name') for f in table.findall(NS+'FIELD')]
    rows=[]
    for tr in table.findall('.//'+NS+'TR'):
        cells=[''.join(c.itertext()).strip() for c in tr]
        if len(cells)!=len(names):raise ValueError('Row width mismatch')
        rows.append(dict(zip(names,cells)))
    return rows


def select_diverse(rows, seen, count=5):
    selected=[];projects=set()
    for require_new_project in [True,False]:
        for row in rows:
            key=(row['member_ous_uid'],row['target_name'])
            if key in seen or (require_new_project and row['proposal_id'] in projects):continue
            selected.append(row);seen.add(key);projects.add(row['proposal_id'])
            if len(selected)==count:return selected
    return selected


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    seen=set();selected=[];queries=[]
    cutoff=datetime.now(timezone.utc).date().isoformat()
    for year in [2013,2016,2019,2022,2024]:
        for band,condition in [('lower','frequency < 200'),('higher','frequency >= 200')]:
            label=f'{year}-{band}'
            query=("SELECT DISTINCT TOP 50 proposal_id, member_ous_uid, target_name, band_list "
                   "FROM ivoa.obscore WHERE science_observation='T' AND is_mosaic='T' "
                   f"AND proposal_id LIKE '{year}.%' AND obs_release_date < '{cutoff}' "
                   f"AND {condition} ORDER BY proposal_id, member_ous_uid, target_name")
            url='https://almascience.eso.org/tap/sync?'+urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='votable',MAXREC=51,QUERY=query))
            receipt=dict(stratum=label,query=query)
            try:
                code,raw=_fetch(url)
                (output/f'{label}.xml').write_bytes(raw)
                receipt.update(http_status=code,sha256=sha256(raw).hexdigest())
                if code!=200:raise ValueError(f'HTTP {code}')
                rows=sample_rows(raw);chosen=select_diverse(rows,seen)
                selected.extend(dict(r,stratum=label) for r in chosen)
                receipt.update(status='SAMPLED',pool_rows=len(rows),selected=len(chosen))
            except (OSError,ValueError,ET.ParseError) as exc:receipt.update(status='FAILED',error=str(exc))
            queries.append(receipt);print(label,receipt['status'],receipt.get('selected'),flush=True)
    report=dict(schema_version='mosaic_acquisition_survey_1',selection='BOUNDED_ORDERED_CONVENIENCE_SAMPLE_NOT_ARCHIVE_CENSUS',
                public_before=cutoff,queries=queries,candidates=[],auxiliary_download_bytes=0)
    (output/'selection.json').write_text(json.dumps(dict(queries=queries,candidates=selected),indent=2)+'\n')
    for i,row in enumerate(selected):
        entry=dict(row, scope=('SOLAR_EXCLUDED_FROM_DUPLICATION' if row['target_name'].strip().casefold() == 'sun' else 'TARGET_TYPE_REQUIRES_VALIDATION'));directory=output/f'candidate-{i:03d}';directory.mkdir()
        try:
            products,raw,url=discover_archive_products(row['member_ous_uid'])
            if raw is not None:(directory/'response.xml').write_bytes(raw)
            receipt=dict(schema_version='archive_product_discovery_1',mode='LIVE_METADATA',request_url=url,
                response_file='response.xml' if raw is not None else None,capture_truncated=False,discovery=asdict(products))
            (directory/'discovery.json').write_text(json.dumps(receipt,indent=2)+'\n')
            from alma_duplicate.archive_auxiliary import select_auxiliary
            eligible=[]
            for index,p in enumerate(products.products):
                try:verified,_,_=select_auxiliary(directory/'discovery.json',index)
                except (ValueError,OSError):continue
                eligible.append(dict(row=index,bytes=verified.content_length))
            entry.update(products_status=products.status,eligible_products=eligible,
                         status='NO_USABLE_PRODUCT' if not eligible else 'AMBIGUOUS_PRODUCTS' if len(eligible)>1 else 'PRODUCT_AVAILABLE_NOT_INSPECTED')
        except (OSError,ValueError) as exc:entry.update(status='REQUEST_FAILED',error=str(exc))
        report['candidates'].append(entry)
        (output/'survey.json').write_text(json.dumps(report,indent=2)+'\n')
        print(i+1,len(selected),entry['status'],flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    run(args.output_dir)
