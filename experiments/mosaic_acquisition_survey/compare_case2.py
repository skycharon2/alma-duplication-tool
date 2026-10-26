"""Reproduce diagnostic comparison using the captured CASE2 acceptance evidence."""
import argparse
import json
from pathlib import Path

from alma_duplicate.mosaic_region_experiment import compare_region
from tests.integration.test_case2_mosaic_acceptance import assess_case, captured_metadata


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    summary=[]
    for member in ['X9c3','X9c5']:
        assessment=assess_case(member);metadata=captured_metadata(member)
        for i,context in enumerate(assessment['contexts']):
            row=metadata.rows[i]
            report=compare_region(row['s_region'],context['coverage']['circles'])
            report.update(member=member,context_id=context['context_id'],frequency_ghz=row['frequency'],
                          scope='METADATA_BOUND_EXECUTION_SUBSET',s_region=row['s_region'])
            (output/f'{member}-{i}.json').write_text(json.dumps(report,indent=2)+'\n')
            summary.append({k:report[k] for k in ['member','context_id','frequency_ghz','counts','sample_count']})
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir)
