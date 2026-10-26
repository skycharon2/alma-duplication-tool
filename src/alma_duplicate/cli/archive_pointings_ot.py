"""Export one verified Archive execution as an OT test pointing list."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from alma_duplicate.archive_mosaic_pointings import load_package_executions
from alma_duplicate.parsers.ot_pointings import parse_ot_pointings


def export_execution(package, asdm, output):
    """Keep science FIELD rows separate and retain their evidence mapping."""
    executions, provenance = load_package_executions(Path(package))
    selected = [e for e in executions if e['asdm_uid'] == asdm]
    if len(selected) != 1:
        raise ValueError('Select exactly one verified ASDM')
    execution = selected[0]
    fields = execution['evidence']['fields']
    raw = ('RA,Dec,Coordinate Type,Coordinate Units\n'
           '--   This signals end of the header\n' + ''.join(
               f"{f['ra_deg']!r},{f['dec_deg']!r},Absolute,DEGREES\n"
               for f in fields)).encode()
    parsed = parse_ot_pointings(raw)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'pointings.txt').write_bytes(raw)
    receipt = dict(schema_version='archive_ot_test_export_1',
                   purpose='CONSTRUCTED_TEST_PROPOSAL_NOT_ORIGINAL_OT_EXPORT',
                   project_code=execution['project_code'],
                   member_ous_uid=execution['member_ous_uid'],
                   source_name=execution['source_name'], asdm_uid=asdm,
                   pointing_count=len(parsed['points']),
                   rows=[dict(row=i, field_id=f['field_id'])
                         for i, f in enumerate(fields, 1)],
                   pointings_sha256=sha256(raw).hexdigest(), provenance=provenance,
                   completeness='SELECTED_EXECUTION_NOT_WHOLE_MEMBER',
                   policy_status='NOT_EVALUATED')
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-audit-dir', required=True, type=Path)
    parser.add_argument('--asdm', required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        report = export_execution(args.package_audit_dir, args.asdm, args.output_dir)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'{exc}\n')
    print(f"EXPORTED: {report['pointing_count']} pointings; {args.output_dir}")


if __name__ == '__main__':
    main()
