"""Inspect verified SPWs or export explicit pairs for proposed Mosaic coverage."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.mosaic_spw_catalog import build_spw_catalog, select_spws


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-audit-dir',type=Path,required=True)
    parser.add_argument('--array-catalog',type=Path,required=True)
    parser.add_argument('--hpbw-coefficient',type=float,required=True)
    parser.add_argument('--assume-uniform-field-antennas',action='store_true')
    parser.add_argument('--select',nargs=2,action='append',metavar=('ASDM','SPW'))
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.hpbw_coefficient) or args.hpbw_coefficient <= 0:
            raise ValueError('HPBW coefficient must be finite and positive')
        readiness = build_readiness(args.package_audit_dir,array_catalog=args.array_catalog)
        catalog = build_spw_catalog(readiness,hpbw_coefficient=args.hpbw_coefficient,
            assume_uniform_field_antennas=args.assume_uniform_field_antennas)
        report = catalog
        if args.select:
            report = select_spws(catalog,[dict(asdm_uid=uid,spw_id=int(sid)) for uid,sid in args.select])
        with args.output.open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    except (OSError,ValueError,KeyError,TypeError,ET.ParseError) as exc:
        parser.exit(2,f'SPW catalog failed: {exc}\n')
    if args.select:
        print(f'SELECTED: {len(report)} pairs; {args.output}')
    else:
        for row in catalog['entries']:
            detail = (f"{row['frequency_hz']/1e9:.9f} GHz; {row['field_count']} fields"
                      if row['status']=='AVAILABLE' else row['reason'])
            print(f"{row['asdm_uid']} SPW {row['spw_id']}: {row['status']} {detail}")
        print(f'CATALOG: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
