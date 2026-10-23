"""Export local Archive Mosaic execution evidence without network access."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from alma_duplicate.archive_mosaic import reconstruct_archive_mosaic


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--listobs', type=Path, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--member', required=True)
    parser.add_argument('--asdm', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--metadata-reference', required=True)
    parser.add_argument('--array', choices=('7m', '12m'))
    parser.add_argument('--array-evidence-reference')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = reconstruct_archive_mosaic(
            args.listobs.read_bytes(), project_code=args.project,
            member_ous_uid=args.member, asdm_uid=args.asdm,
            source_name=args.source, metadata_reference=args.metadata_reference,
            array_label=args.array, array_evidence_reference=args.array_evidence_reference,
        )
        document = {'schema_version': 'archive_mosaic_execution_1',
                    'execution': asdict(result)}
        # Exclusive creation preserves earlier evidence exports.
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Archive Mosaic export failed: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
