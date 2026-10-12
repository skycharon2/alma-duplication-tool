"""Diagnostic bytes agree with the actual publication serializer."""
from copy import deepcopy
import json

import pytest

from alma_duplicate.report_size import analyze_report
from alma_duplicate.reporting import report_json_text
from alma_duplicate.cli.analyze_report_size import main


@pytest.mark.parametrize('document', [
    {}, {'empty': [[], {}, None]},
    {'unicode': '天文☄️', 'escaped': 'quote"\n\\', 'number': 1.25e-20},
    {'nested': [{'a': 1, 'b': [True, False, 0, -5]}, {'more': {'x': [1, 2]}}]},
])
def test_exact_bytes_and_root_partition(document):
    result = analyze_report(document)
    assert result['formatted_bytes'] == len(report_json_text(document).encode('utf-8'))
    assert result['compact_bytes'] == len((json.dumps(
        document, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode())
    assert sum(result['root_value_bytes'].values()) + result['root_structure_bytes'] == result['formatted_bytes']


def test_repeated_content_at_different_depths_without_raw_values_or_mutation():
    evidence = {'message': 'private scientific payload' * 200, 'unit': 'MHz'}
    document = {'context_evaluations': [{'evidence': evidence},
                                       {'nested': {'evidence': deepcopy(evidence)}}]}
    before = deepcopy(document)
    result = analyze_report(document)
    repeated, = [item for item in result['repeated_containers']
                 if item['example_paths'][0].endswith('/0/evidence')]
    assert repeated['occurrences'] == 2
    assert repeated['example_paths'] == ['/context_evaluations/0/evidence',
                                         '/context_evaluations/1/nested/evidence']
    assert repeated['repeated_compact_bytes'] == len(json.dumps(evidence, separators=(',', ':')).encode())
    assert 'private scientific payload' not in json.dumps(result)
    assert document == before
    assert result['formatted_bytes'] == len(report_json_text(document).encode())


def test_file_analysis_does_not_overwrite_or_reformat_input(tmp_path):
    source, output = tmp_path / 'report.json', tmp_path / 'size.json'
    raw = b'{"version":5,"context_evaluations":[]}'
    source.write_bytes(raw)
    assert main([str(source), '--output', str(output)]) == 0
    result = json.loads(output.read_text())
    assert result['input_bytes'] == len(raw)
    assert not result['input_size_matches_publication_format']
    with pytest.raises(SystemExit):
        main([str(source), '--output', str(output)])
    assert source.read_bytes() == raw
