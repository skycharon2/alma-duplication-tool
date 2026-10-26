"""Inspect a size-biased subset under a 200 MB aggregate reservation budget."""
import argparse
import json
from pathlib import Path
from alma_duplicate.mosaic_candidate_preparation import prepare_candidates
from alma_duplicate.mosaic_resource_limits import MosaicResourceLimits


def run(survey,output):
    rows=json.loads(Path(survey).read_text())['candidates']
    eligible=[r for r in rows if r['target_name'].strip().casefold() != 'sun' and len(r.get('eligible_products',[]))==1
              and isinstance(r['eligible_products'][0]['bytes'],int)
              and 0<r['eligible_products'][0]['bytes']<=100_000_000]
    eligible.sort(key=lambda r:r['eligible_products'][0]['bytes'])
    selected=[];strata=set();remaining=200_000_000
    for row in eligible:
        size=row['eligible_products'][0]['bytes']
        if row['stratum'] in strata or size>remaining:continue
        selected.append(row);strata.add(row['stratum']);remaining-=size
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    summary=[]
    for i,row in enumerate(selected):
        # Advertised-size reservation is also an enforced per-package download cap.
        size=row['eligible_products'][0]['bytes']
        discovery=dict(schema_version='mosaic_candidate_discovery_1',status='EXPLICIT_SURVEY_SUBSET',
            candidates=[dict(context_id=str(i),member_ous_uid=row['member_ous_uid'],
                source_name=row['target_name'],project_code=row['proposal_id'],geometry_flags=['T'])])
        report=prepare_candidates(discovery,output=output/f'candidate-{i:03d}',cache='data/cache/archive-auxiliary',
            max_candidates=1,resource_limits=MosaicResourceLimits(size,250_000_000,1_000_000_000))
        summary.append(dict(sample=row,reserved_download_bytes=size,result=report['candidates'][0]))
        (output/'inspection.json').write_text(json.dumps(dict(total_reserved_bytes=200_000_000-remaining,
            selection='SMALL_PACKAGE_STRATUM_SUBSET_NOT_UNBIASED_SUCCESS_RATE',candidates=summary),indent=2)+'\n')
        print(row['stratum'],report['candidates'][0]['status'],report['candidates'][0].get('error'),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--survey',required=True);p.add_argument('--output-dir',required=True)
    a=p.parse_args();run(a.survey,a.output_dir)
