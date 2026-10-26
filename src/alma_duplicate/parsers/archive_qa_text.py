"""Inspect legacy QA fields and scans without promoting coordinates to ICRS."""
import re

from alma_duplicate.parsers.archive_listobs import hms_degrees, dms_degrees

FIELD = re.compile(r'^\s*(\d+)\s+(\d+)\s+(\S+)\s+(\d+:\d+:\d+(?:\.\d+)?)\s+([+-]\d+\.\d+\.\d+(?:\.\d+)?)\s+\S+\s+\d+\s*$')
SCAN = re.compile(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+\d+:\d+:[\d.]+\s+-\s+\d+:\d+:[\d.]+\s+\S+\s+\S+\s+(.+?)\s*$')
MS = re.compile(r'uid___(A[0-9A-Za-z]+)_([0-9A-Za-z]+)_([0-9A-Za-z]+)\.ms\.split')


def inspect_qa_text(raw: bytes, *, target_name: str) -> dict:
    """Use FIELD/source IDs to resolve truncated scan names; retain blockers.

    Matching a truncated prefix is only a consistency check after the numeric
    FIELD and source IDs match. It never selects a target by prefix alone.
    """
    text = raw.decode('utf-8')
    headers = re.findall(r'^\s*SUMMARY INFORMATION FOR\s+(\S+)\s*$', text, re.M)
    result = dict(status='UNSUPPORTED_QA_LAYOUT', measurement_sets=headers,
                  fields=[], science_fields=[], excluded_fields=[],
                  position_status='NOT_READY', policy_status='NOT_EVALUATED',
                  reasons=['LEGACY_QA_LAYOUT_NOT_VALIDATED'])
    try:
        if len(headers) != 1 or any(text.count(x) != 1 for x in
                ('SCAN LISTING', 'FIELD INFORMATION', 'FREQUENCY INFORMATION')):
            return result
        ms = MS.fullmatch(headers[0])
        processed = re.findall(r'^\s*Processed from ms:\s+(\S+)\s*$', text, re.M)
        if not ms or processed != headers:
            raise ValueError('QA_SUMMARY_MS_IDENTITY_CONFLICT')
        result['reported_asdm_uid'] = 'uid://' + '/'.join(ms.groups())
        scan_section, rest = text.split('SCAN LISTING', 1)[1].split('FIELD INFORMATION', 1)
        section = rest.split('FREQUENCY INFORMATION', 1)[0]
        if 'RA  (J2000)' not in section:
            return result
        fields = {}
        for line in section.splitlines():
            if not re.match(r'^\s*\d', line):
                continue
            match = FIELD.fullmatch(line)
            if match is None:
                raise ValueError('QA_FIELD_ROW_UNPARSED')
            fid, sid, name, ra, dec = match.groups()
            fid = int(fid)
            if fid in fields:
                raise ValueError('QA_DUPLICATE_FIELD_ID')
            # Validate ranges, retaining native strings and frame, not ICRS values.
            hms_degrees(ra)
            dms_degrees(dec)
            fields[fid] = dict(field_id=fid, source_id=int(sid), target_name=name,
                               ra_original=ra, dec_original=dec, reported_frame='J2000')
        science = {}
        for line in scan_section.splitlines():
            if not re.match(r'^\s*\d', line):
                continue
            match = SCAN.fullmatch(line)
            if match is None:
                raise ValueError('QA_SCAN_ROW_UNPARSED')
            scan, fid, sid, name, intent = match.groups()
            fid = int(fid)
            field = fields.get(fid)
            if field is None or field['source_id'] != int(sid):
                raise ValueError('QA_SCAN_FIELD_IDENTITY_CONFLICT')
            actual = field['target_name']
            if name != actual and not (name.endswith('*') and len(name) > 1 and actual.startswith(name[:-1])):
                raise ValueError('QA_SCAN_FIELD_NAME_CONFLICT')
            if intent == 'Obs Target':
                science.setdefault(fid, set()).add(int(scan))
            elif not intent.startswith('Cal '):
                raise ValueError('QA_SCAN_INTENT_UNSUPPORTED')
        result['fields'] = [f for f in fields.values() if f['target_name'] == target_name]
        result['science_fields'] = [dict(f, scan_ids=sorted(science[f['field_id']]))
                                   for f in result['fields'] if f['field_id'] in science]
        result['excluded_fields'] = [dict(f, reason='NO_OBS_TARGET_SCAN')
                                    for f in result['fields'] if f['field_id'] not in science]
        result.update(status='LEGACY_QA_SCIENCE_FIELDS_IDENTIFIED' if result['science_fields'] else 'TARGET_SCIENCE_FIELDS_NOT_FOUND',
            scan_binding='QA_LOCAL_FIELD_AND_SOURCE_IDS',
            reasons=['FRAME_RELABEL_APPLICABILITY_NOT_VALIDATED',
                     'SPLIT_MS_IDENTITY_NOT_INDEPENDENTLY_VALIDATED',
                     'INDEPENDENT_COORDINATE_REFERENCE_MISSING',
                     'HISTORICAL_COORDINATE_QUALITY_NOT_VERIFIED'])
    except ValueError as exc:
        result.update(status='INVALID_QA_EVIDENCE', fields=[], science_fields=[], excluded_fields=[],
                      reasons=[str(exc)])
    return result
