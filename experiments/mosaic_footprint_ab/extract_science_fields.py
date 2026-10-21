"""Extract observed science FIELD centres from a CASA listobs text snapshot.

The script cross-checks ON_SOURCE scan rows against the FIELD table.
It does not infer original OT pointing intent or Member-wide completeness.
Standard library only.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
import re

from compare import read_tap

COLUMNS = [
    "project_code", "member_ous_uid", "asdm_uid", "measurement_set", "array",
    "field_id", "source_id", "target_name", "frame", "ra_hms", "dec_dms",
    "ra_deg", "dec_deg", "ms_nrows", "science_scan_count", "science_scan_ids",
    "observed_spw_ids", "science_intent",
]
FIELD = re.compile(
    r"^\s*(\d+)\s+\S+\s+(\S+)\s+"
    r"(\d{1,2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
    r"([+-]\d{2}\.\d{2}\.\d{2}(?:\.\d+)?)\s+"
    r"(ICRS)\s+(\d+)\s+(\d+)\s*$"
)
SCAN = re.compile(
    r"\s(\d+)\s+(\d+)\s+(\S+)\s+\d+\s+\[([0-9,]+)\]"
)


def hms_degrees(hms: str) -> float:
    hh, mm, sec = hms.split(":")
    h, m, s = int(hh), int(mm), float(sec)
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
        raise ValueError(f"Invalid RA: {hms}")
    return 15.0 * (h + m / 60 + s / 3600)


def dms_degrees(dms: str) -> float:
    sign = -1 if dms.startswith("-") else 1
    degrees, minutes, seconds = dms[1:].split(".", 2)
    d, m, s = int(degrees), int(minutes), float(seconds)
    if not (0 <= d <= 90 and 0 <= m < 60 and 0 <= s < 60):
        raise ValueError(f"Invalid Dec: {dms}")
    if d == 90 and (m or s):
        raise ValueError(f"Invalid Dec: {dms}")
    return sign * (d + m / 60 + s / 3600)


def extract(listobs: str, *, tap_row: dict, array: str) -> list[dict]:
    if array not in {"7m", "12m"}:
        raise ValueError("Expected 7m or 12m array")
    asdm_tag = tap_row["asdm_uid"].replace(":", "_").replace("/", "_") + ".ms"
    # Locate the actual header, including in Markdown-wrapped snapshots.
    # Require one exact MS basename; a mention elsewhere is not source binding.
    headers = re.findall(
        r"^\s*MeasurementSet Name:\s+(.+?)\s+MS Version\s+\S+\s*$",
        listobs, re.M,
    )
    if len(headers) != 1 or Path(headers[0].strip()).name != asdm_tag:
        raise ValueError("Listobs MeasurementSet does not match TAP ASDM")
    declared = re.search(r"^Fields:\s*(\d+)\s*$", listobs, re.M)
    if declared is None or "Spectral Windows:" not in listobs:
        raise ValueError("Missing listobs FIELD table")
    scan_section, remaining = listobs.split(declared.group(0), 1)
    fields_section = remaining.split("Spectral Windows:", 1)[0]

    scans_by_field: dict[int, set[int]] = defaultdict(set)
    spws_by_field: dict[int, set[int]] = defaultdict(set)
    for line in scan_section.splitlines():
        if "OBSERVE_TARGET#ON_SOURCE" not in line:
            continue
        m = SCAN.search(line)
        if m is None:
            raise ValueError(f"Unparsed ON_SOURCE scan: {line[:100]}")
        scan_id, field_id, name, spws = m.groups()
        if name != tap_row["target_name"]:
            raise ValueError(f"ON_SOURCE target mismatch: {name}")
        field_id = int(field_id)
        scans_by_field[field_id].add(int(scan_id))
        spws_by_field[field_id].update(int(x) for x in spws.split(","))
    if not scans_by_field:
        raise ValueError("No ON_SOURCE science scan rows")

    listed_fields = {}
    for line in fields_section.splitlines():
        m = FIELD.match(line)
        if m:
            fid = int(m.group(1))
            if fid in listed_fields:
                raise ValueError("Repeated FIELD_ID in FIELD table")
            listed_fields[fid] = m.groups()
    if len(listed_fields) != int(declared.group(1)):
        raise ValueError(f"FIELD table incomplete: {len(listed_fields)} of {declared.group(1)}")
    if not scans_by_field.keys() <= listed_fields.keys():
        raise ValueError("ON_SOURCE references a missing FIELD_ID")

    output = []
    for fid in sorted(scans_by_field):
        _, name, ra_hms, dec_dms, frame, src_id, nrows = listed_fields[fid]
        if name != tap_row["target_name"] or frame != "ICRS":
            raise ValueError(f"Science FIELD {fid} name/frame mismatch")
        scan_ids = sorted(scans_by_field[fid])
        output.append({
            "project_code": tap_row["proposal_id"],
            "member_ous_uid": tap_row["member_ous_uid"],
            "asdm_uid": tap_row["asdm_uid"],
            "measurement_set": asdm_tag,
            "array": array,
            "field_id": fid,
            "source_id": int(src_id),
            "target_name": name,
            "frame": frame,
            "ra_hms": ra_hms,
            "dec_dms": dec_dms,
            "ra_deg": f"{hms_degrees(ra_hms):.14f}",
            "dec_deg": f"{dms_degrees(dec_dms):.14f}",
            "ms_nrows": int(nrows),
            "science_scan_count": len(scan_ids),
            "science_scan_ids": ";".join(map(str, scan_ids)),
            "observed_spw_ids": ";".join(map(str, sorted(spws_by_field[fid]))),
            "science_intent": "OBSERVE_TARGET#ON_SOURCE",
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listobs", type=Path, required=True)
    parser.add_argument("--tap", type=Path, required=True)
    parser.add_argument("--array", choices=("7m", "12m"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = extract(args.listobs.read_text(encoding="utf-8"), tap_row=read_tap(args.tap), array=args.array)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Science fields: {len(rows)} | FIELD_IDs: {[r['field_id'] for r in rows]}")
    print(f"Scan appearances: {sum(r['science_scan_count'] for r in rows)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
