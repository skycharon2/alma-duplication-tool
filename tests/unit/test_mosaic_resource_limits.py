import argparse
import pytest
from alma_duplicate.mosaic_resource_limits import (
    MosaicResourceLimits, add_resource_arguments, resource_arguments,
)


@pytest.mark.parametrize('field,value', [('max_download_bytes', True),
    ('max_download_bytes', 1_000_000_001), ('max_weblog_bytes', 0),
    ('max_expanded_bytes', 10_000_000_001)])
def test_invalid_limits(field, value):
    with pytest.raises(ValueError):
        MosaicResourceLimits(**{field: value})


def test_cli_limits_and_defaults():
    parser = argparse.ArgumentParser()
    add_resource_arguments(parser, 'mosaic-')
    assert resource_arguments(parser.parse_args([]), 'mosaic_') == MosaicResourceLimits()
    args = parser.parse_args(['--mosaic-max-download-bytes', '900000000'])
    assert resource_arguments(args, 'mosaic_').max_download_bytes == 900000000
