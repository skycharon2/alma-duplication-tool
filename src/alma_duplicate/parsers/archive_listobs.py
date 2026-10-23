"""Parse the supported ICRS, single-target CASA listobs layout offline.

Strict parsing preserves raw precision and scan/SPW links. A complete FIELD
section does not prove complete acquisition, execution coverage, or policy scope.
"""
from collections import defaultdict
from hashlib import sha256
from pathlib import PurePosixPath as Path
import re

from alma_duplicate.domain.archive_mosaic import (
    ParsedScienceFields, ScienceField, ScienceScan,
)

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


def _extract(listobs: str, *, asdm_uid: str, target_name: str) -> tuple[list[ScienceField], int]:
    asdm_tag = asdm_uid.replace(":", "_").replace("/", "_") + ".ms"
    # Locate the actual header, including in Markdown-wrapped snapshots.
    # Require one exact MS basename; a mention elsewhere is not source binding.
    headers = re.findall(
        r"^\s*MeasurementSet Name:\s+(.+?)\s+MS Version\s+\S+\s*$",
        listobs, re.M,
    )
    if len(headers) != 1 or Path(headers[0].strip()).name != asdm_tag:
        raise ValueError("Listobs MeasurementSet does not match TAP ASDM")
    declarations = re.findall(r"^Fields:\s*(\d+)\s*$", listobs, re.M)
    if len(declarations) != 1:
        raise ValueError("Expected one FIELD table")
    declared = re.search(r"^Fields:\s*(\d+)\s*$", listobs, re.M)
    if declared is None or "Spectral Windows:" not in listobs:
        raise ValueError("Missing listobs FIELD table")
    scan_section, remaining = listobs.split(declared.group(0), 1)
    fields_section = remaining.split("Spectral Windows:", 1)[0]

    scans_by_field: dict[int, set[int]] = defaultdict(set)
    scans = {}
    for line in scan_section.splitlines():
        if "OBSERVE_TARGET#ON_SOURCE" not in line:
            continue
        m = SCAN.search(line)
        if m is None:
            raise ValueError(f"Unparsed ON_SOURCE scan: {line[:100]}")
        scan_id, field_id, name, spws = m.groups()
        if name != target_name:
            raise ValueError(f"ON_SOURCE target mismatch: {name}")
        field_id = int(field_id)
        scan_id = int(scan_id)
        key = (field_id, scan_id)
        entry = tuple(int(x) for x in spws.split(","))
        if key in scans and scans[key] != entry:
            raise ValueError("Conflicting science scan identity")
        scans[key] = entry
        scans_by_field[field_id].add(scan_id)
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
        if name != target_name or frame != "ICRS":
            raise ValueError(f"Science FIELD {fid} name/frame mismatch")
        scan_ids = sorted(scans_by_field[fid])
        output.append(ScienceField(
            field_id=fid, source_id=int(src_id), target_name=name, frame=frame,
            ra_original=ra_hms, dec_original=dec_dms,
            ra_deg=hms_degrees(ra_hms), dec_deg=dms_degrees(dec_dms),
            scans=tuple(ScienceScan(sid, scans[(fid, sid)]) for sid in scan_ids),
        ))
    return output, int(declared.group(1))



def parse_science_fields(raw: bytes, *, asdm_uid: str, target_name: str) -> ParsedScienceFields:
    """Reject unsupported or mismatched input with ValueError; perform no I/O."""
    if not re.fullmatch(r"uid://A[0-9A-Za-z]+/[0-9A-Za-z]+/[0-9A-Za-z]+", asdm_uid):
        raise ValueError("Invalid ASDM UID")
    if not target_name or target_name != target_name.strip():
        raise ValueError("Expected nonblank exact target name")
    fields, count = _extract(raw.decode("utf-8"), asdm_uid=asdm_uid, target_name=target_name)
    return ParsedScienceFields(
        measurement_set=asdm_uid.replace(":", "_").replace("/", "_") + ".ms",
        source_sha256=sha256(raw).hexdigest(), fields=tuple(fields),
        declared_field_count=count,
    )
