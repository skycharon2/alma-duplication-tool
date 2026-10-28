"""Repeatable CASE2 backend acceptance; offline transport is fixture-derived."""
import argparse
from datetime import datetime
from functools import partial
import json
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from alma_duplicate.clients import archive_contract as contract
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.mosaic_candidate_discovery import discover_candidates, plan_discovery
from alma_duplicate.proposed_mosaic import import_proposed
from alma_duplicate.submitted_line_assessment import assess_submitted_line_mosaic_search_v2

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/archive/case2_mosaic_2026_10_26'
POINTINGS = ROOT / 'examples/mosaic/case2/ngc253-X9c3-pointings.txt'
REQUEST = ROOT / 'examples/mosaic/case2/submitted-line-v2-request.json'


def load_metadata(member):
    saved = json.loads((FIXTURES / member / 'metadata.json').read_text())
    p = saved['provenance']
    for name in ('started_at', 'finished_at'):
        p[name] = datetime.fromisoformat(p[name])
    p['normalized_parameters'] = tuple(tuple(v) for v in p['normalized_parameters'])
    projection = p['projection']
    projection['optional_columns'] = tuple(contract.ArchiveOptionalColumnEvidence(**v)
                                          for v in projection['optional_columns'])
    p['projection'] = contract.ArchiveProjectionEvidence(**projection)
    return contract.ArchiveQueryResult(
        status=contract.ArchiveQueryStatus(saved['status']), rows=tuple(saved['rows']),
        provenance=contract.ArchiveQueryProvenance(**p),
        field_metadata=tuple(contract.TapFieldMetadata(**f) for f in saved['field_metadata']),
    )


class FixtureArchive:
    """Two captured Members, not a replay of an exhaustive Archive search."""

    def __init__(self, proposed):
        if proposed['input_sha256'] != sha256(POINTINGS.read_bytes()).hexdigest():
            raise ValueError('Offline discovery is bound to the original CASE2 pointing bytes')
        self.metadata = {m: load_metadata(m) for m in ('X9c3', 'X9c5')}
        self.plan = plan_discovery(proposed, margin_arcsec=0)
        self.urls = {r['url'] for r in self.plan['requests']}
        self.fetched = []
        self.queried = []

    def fetch(self, url):
        if url not in self.urls:
            raise ValueError('Unexpected discovery query or pointings')
        self.fetched.append(url)
        query = parse_qs(urlsplit(url).query)['QUERY'][0]
        fields = ('proposal_id', 'member_ous_uid', 'asdm_uid', 'target_name',
                  'science_observation', 'is_mosaic')
        root = ET.Element('VOTABLE', xmlns='http://www.ivoa.net/xml/VOTable/v1.3')
        resource = ET.SubElement(root, 'RESOURCE', type='results')
        ET.SubElement(resource, 'INFO', name='QUERY_STATUS', value='OK')
        table = ET.SubElement(resource, 'TABLE')
        for field in fields:
            ET.SubElement(table, 'FIELD', name=field, datatype='char', arraysize='*')
        data = ET.SubElement(ET.SubElement(table, 'DATA'), 'TABLEDATA')
        # All original CASE2 points lie inside these captured regions. The null
        # fallback has no rows in this deliberately bounded fixture universe.
        if 's_region IS NULL' not in query:
            identities = {tuple(r[f] for f in fields)
                          for metadata in self.metadata.values() for r in metadata.rows}
            for values in sorted(identities):
                row = ET.SubElement(data, 'TR')
                for value in values:
                    ET.SubElement(row, 'TD').text = value
        return 200, ET.tostring(root)

    def search(self, spec):
        member = spec.member_ous_uid.split('/')[-1]
        if member not in self.metadata or spec.target_name != 'NGC253':
            raise ValueError('Unexpected candidate metadata query')
        result = self.metadata[member]
        if any(r['member_ous_uid'] != spec.member_ous_uid for r in result.rows):
            raise ValueError('Metadata Member mismatch')
        self.queried.append((spec.member_ous_uid, spec.target_name))
        return result


def run(output, *, pointings=POINTINGS, live=False, raw_request=None):
    raw_request = raw_request or json.loads(REQUEST.read_text())['request']
    proposed = import_proposed(Path(pointings).read_bytes(),
        source_name=raw_request['target_name'], array='12m',
        confirm_fixed_icrs=True, confirm_complete=True)
    fixture = None if live else FixtureArchive(proposed)
    result = assess_submitted_line_mosaic_search_v2(
        raw_request, MosaicAssessmentInput(proposed, Path(output), None, 0),
        archive_client=fixture,
        discovery_provider=None if live else partial(discover_candidates, fetch=fixture.fetch),
    )
    summary = dict(mode='LIVE_ARCHIVE' if live else 'FIXTURE_DERIVED_DISCOVERY',
                   assessment_status=result['assessment_status'],
                   pointing_sha256=proposed['input_sha256'],
                   candidate_count=len(result['candidates']), contexts=[])
    for candidate in result['candidates']:
        for context in candidate.get('evaluation', {}).get('contexts', []):
            summary['contexts'].append(dict(
                member=candidate['member_ous_uid'], context_id=context['context_id'],
                reference=context['source_reference'],
                inside=context['coverage']['inside_count'],
                total=context['coverage']['pointing_count'],
                truth=context['branches'][0]['truth'],
                criteria={c['criterion_id']: c['outcome']
                          for c in context['line_pairs'][0]['criteria']},
            ))
    Path(output, 'acceptance-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return result, summary, fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--pointings', type=Path, default=POINTINGS)
    parser.add_argument('--live', action='store_true', help='Query Archive without a project filter')
    args = parser.parse_args()
    _, summary, _ = run(args.output_dir, pointings=args.pointings, live=args.live)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
