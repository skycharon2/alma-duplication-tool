"""Reference ownership and conditional mapping boundaries."""
import subprocess
import sys
from dataclasses import asdict

from alma_duplicate import queue_processor_mode as experiment
from alma_duplicate import queue_mode_reference as reference


def test_compatibility_exports_share_reference_objects():
    for name in ('Configuration', 'configurations', 'match', 'consensus',
                 'configuration_record', 'MAPPING_SOURCES', 'EXTRA_RESPONSES'):
        assert getattr(experiment, name) is getattr(reference, name)


def test_formal_adapter_does_not_import_diagnostic_modules():
    subprocess.run([sys.executable, '-c', '''
import sys
import alma_duplicate.queue_mode_adapter
assert 'alma_duplicate.queue_processor_mode' not in sys.modules
assert 'alma_duplicate.queue_mode' not in sys.modules
'''], check=True)


def test_mapping_preserves_input_and_separates_counterpart_bandwidth():
    c = next(c for c in reference.configurations(13)
             if c.quantization == '4X4' and c.bandwidth_mhz == 250)
    original = asdict(c)
    mapping = reference.map_tp_counterpart(c)
    assert mapping.reasons == ()
    assert mapping.counterpart.counterpart_nominal_bandwidth_mhz == 1000
    assert mapping.counterpart.counterpart_resolution_mhz == c.resolution_mhz
    assert mapping.counterpart.native_mode is None
    assert asdict(c) == original


def test_mapping_keeps_applicability_gaps():
    full = next(c for c in reference.configurations(13) if c.polarization == 'FULL')
    wide = next(c for c in reference.configurations(13)
                if c.quantization == '4X4' and c.bandwidth_mhz == 1000)
    for c, reason in ((full, 'FULL_POLARIZATION_TP_UNSUPPORTED'),
                      (wide, 'TP_COUNTERPART_EXCEEDS_SUPPORTED_BASEBAND')):
        result = reference.map_tp_counterpart(c)
        assert result.counterpart is None
        assert result.reasons == (reason,)
