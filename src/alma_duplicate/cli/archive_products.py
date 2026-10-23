"""Discover Member DataLink products or replay a captured response."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.clients.archive_products import (
    MAX_RESPONSE_BYTES, discover_archive_products, parse_archive_products,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--member', required=True)
    parser.add_argument('--asdm')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--response', type=Path, help='Replay saved DataLink XML offline')
    source.add_argument('--live', action='store_true', help='Fetch metadata only')
    parser.add_argument('--origin', choices=ARCHIVE_ORIGINS, default=ARCHIVE_ORIGINS[0])
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # Reserve a new receipt directory before any source access.
        args.output_dir.mkdir(parents=False, exist_ok=False)
        started = datetime.now(timezone.utc).isoformat()
        if args.live:
            result, raw, url = discover_archive_products(
                args.member, asdm_uid=args.asdm, origin=args.origin,
            )
        else:
            with args.response.open('rb') as stream:
                raw = stream.read(MAX_RESPONSE_BYTES + 1)
            result = parse_archive_products(raw, member_ous_uid=args.member, asdm_uid=args.asdm)
            url = None
        finished = datetime.now(timezone.utc).isoformat()
        document = {
            'schema_version': 'archive_product_discovery_1',
            'mode': 'LIVE_METADATA' if args.live else 'OFFLINE_REPLAY',
            'request_url': url,
            'input_path': str(args.response.resolve()) if args.response else None,
            'recorded_at': finished,
            'request_started_at': started if args.live else None,
            'request_finished_at': finished if args.live else None,
            'historical_acquisition_time': None,
            'response_file': 'response.xml' if raw is not None else None,
            'capture_truncated': raw is not None and len(raw) > MAX_RESPONSE_BYTES,
            'discovery': asdict(result),
        }
        if raw is not None:
            (args.output_dir / 'response.xml').write_bytes(raw)
        (args.output_dir / 'discovery.json').write_text(
            json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + '\n',
            encoding='utf-8',
        )
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Product discovery failed: {exc}\n')
    print(f'{result.status}: {len(result.products)} product records; receipt: {args.output_dir}')
    return 0 if result.status in ('DISCOVERED', 'EMPTY') else 3


if __name__ == '__main__':
    raise SystemExit(main())
