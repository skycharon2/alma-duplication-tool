"""Spatial adaptation must not import selection dispatch back into its callers."""
import importlib
import subprocess
import sys

import pytest


@pytest.mark.parametrize('name', ['adapt_spatial', '_text', '_coordinate', '_archive_center', '_circle'])
def test_historical_spatial_paths_export_the_owned_function(name):
    legacy = importlib.import_module('alma_duplicate.spatial')
    owner = importlib.import_module('alma_duplicate.spatial_evidence')
    assert getattr(legacy, name) is getattr(owner, name)


@pytest.mark.parametrize('module', ['spatial_evidence', 'queue_position'])
def test_adaptation_and_queue_strategy_do_not_load_dispatch(module):
    subprocess.run([sys.executable, '-c', f'''
import importlib
import sys
importlib.import_module('alma_duplicate.{module}')
assert 'alma_duplicate.spatial' not in sys.modules
assert 'alma_duplicate.search_plan' not in sys.modules
assert 'alma_duplicate.candidate_search' not in sys.modules
'''], check=True)


@pytest.mark.parametrize('order', [
    ('spatial_evidence', 'queue_position', 'spatial'),
    ('queue_position', 'spatial', 'spatial_evidence'),
    ('spatial', 'spatial_evidence', 'queue_position'),
])
def test_public_import_orders_have_no_partial_initialization(order):
    subprocess.run([sys.executable, '-c', f'''
import importlib
for name in {order!r}:
    importlib.import_module('alma_duplicate.' + name)
from alma_duplicate.spatial import adapt_spatial, evaluate_spatial
from alma_duplicate.spatial_evidence import adapt_spatial as owned
from alma_duplicate.queue_position import adapt_queue_position
assert adapt_spatial is owned
assert callable(evaluate_spatial) and callable(adapt_queue_position)
'''], check=True)
