"""Versioned, conditional BLC signature catalog for offline Queue diagnostics.

This is a forward enumeration of a documented subset of configurations.
It is NOT an inverse channel-count estimate and not an operational setup validator.
See docs/queue_mode_census.md for the explicit scope and response provenance.
"""

from __future__ import annotations

from functools import lru_cache

from alma_duplicate.domain.queue_mode import QueueModeConfiguration

CATALOG_VERSION = "blc_queue_signature_catalog_1"
PROJECT_CYCLES = {"2024": 11, "2025": 12, "2026": 13}
CATALOG_SCOPE = "BLC_HANNING_DOUBLE_FULL_STANDARD_2X2_AND_4X4"
SOURCES = {
    "handbook11": {
        "url": "https://almascience.eso.org/documents-and-tools/cycle11/alma-technical-handbook",
        "version": "Doc 11.3, version 1.4, 2024-03-01",
        "sha256": "c8e5a269e0e326459643ca7cf2f1ebe88b9eb57dff9e0c7707d25b398fdb7e33",
        "sections": "5.1.3, 5.5.2, 6.3.2; Tables 5.1 and 5.2",
    },
    "handbook12": {
        "url": "https://almascience.eso.org/documents-and-tools/cycle12/alma-technical-handbook",
        "version": "Doc 12.3, version 1.0, 2025-03-01",
        "sha256": "93f1059c0ae9883928eeda7bf0a1ae028a6d919f042b7f6fa11d77ff7c35f687",
        "sections": "5.1.3, 5.5.2, 6.3.2; Tables 5.1 and 5.2",
    },
    "handbook13": {
        "url": "https://almascience.eso.org/documents-and-tools/cycle13/alma-technical-handbook",
        "version": "Doc 13.3, version 1.0, 2026-03-01",
        "sha256": "4881909132bb20770cc48dfe6bce38a3bb29b2a028a0b320263ddd34c5058c15",
        "sections": "5.1.3, 5.5.2, 6.3.2; Tables 5.1 and 5.2",
    },
    "ot_decoder": {
        "url": "https://asw.alma.cl/ASW/OBSPREP/-/blob/678f32bab95530ad8741817ded1bdde633c95288/ObservingTool/src/alma/obsprep/bo/schedblock/ConfigModeDecoderImpl.java",
        "role": "BLC nominal bandwidth, channel spacing and permitted resource combinations; not a Cycle 11-13 release manifest",
    },
    "ot_response_legacy": {
        "url": "https://asw.alma.cl/ASW/OBSPREP/-/blob/6864764fdd083afb540e83a61de62c3e6500305a/ObservingTool/src/alma/obsprep/bo/enumerations/SpectralAverage.java",
        "role": "Hanning response factors 2, 2.312, 3.97, 7.996, 16; explicitly 12-m scope",
    },
    "ot_response_rounded": {
        "url": "https://asw.alma.cl/ASW/OBSPREP/-/blob/678f32bab95530ad8741817ded1bdde633c95288/ObservingTool/src/alma/obsprep/bo/enumerations/SpectralAverage.java",
        "role": "Hanning response factors 2, 2.312, 4, 8, 16; explicitly 12-m scope",
    },
    "queue_export_n16": {
        "reference": "Queue CSV Derived Mode Method, supplied 2026-09-22, examples B and FULL polarization",
        "role": "Provisional export compatibility: 7.81201171875 / 0.48828125 = 15.999; also FULL 15.6240234375. Not an exact factor from the rounded handbook table or the retrieved OT revisions.",
    },
}
# A response profile is not inferred from project year. Both historical and
# rounded values remain possible; shared numerical signatures are stored once.
RESPONSES = (
    (1, 2.0, "ot_response_legacy+ot_response_rounded"),
    (2, 2.312, "ot_response_legacy+ot_response_rounded"),
    (4, 3.97, "ot_response_legacy"),
    (4, 4.0, "ot_response_rounded"),
    (8, 7.996, "ot_response_legacy"),
    (8, 8.0, "ot_response_rounded"),
    (16, 15.999, "queue_export_n16"),
    (16, 16.0, "ot_response_legacy+ot_response_rounded"),
)
# Maximum supported resource divisor for the non-oversampled 2x2 subset.
# 1875 is the Queue export label for the 2000 MHz baseband configuration.
# Do not construct arbitrary 1875 MHz half/quarter-resource modes.
RESOURCE_DIVISORS = {
    1875.0: (1,),
    1000.0: (1,),
    500.0: (1, 2),
    250.0: (1, 2, 4),
    125.0: (1, 2, 4),
    62.5: (1, 2, 4),
}


@lru_cache(maxsize=3)
def configurations(cycle: int) -> tuple[QueueModeConfiguration, ...]:
    """Return a cycle-keyed catalog; other cycles are deliberately unsupported."""
    if cycle not in (11, 12, 13):
        return ()
    rows = []
    for polarization, products in (("DOUBLE", 2), ("FULL", 4)):
        for bandwidth, divisors in RESOURCE_DIVISORS.items():
            if polarization == "FULL":
                divisors = {
                    1875.0: (1,),
                    1000.0: (1,),
                    500.0: (1,),
                    250.0: (1, 2),
                    125.0: (1, 2, 4),
                    62.5: (1, 2, 4),
                }[bandwidth]
            nominal = 2000.0 if bandwidth == 1875.0 else bandwidth
            for divisor in divisors:
                spacing = nominal / (8192 / products / divisor)
                for averaging, factor, source in RESPONSES:
                    rows.append(
                        QueueModeConfiguration(
                            f"C{cycle}_BLC_{polarization}_{bandwidth:g}_2X2_R{divisor}_N{averaging}_H{factor:g}",
                            cycle,
                            "BLC",
                            polarization,
                            bandwidth,
                            spacing * factor,
                            "FDM",
                            averaging,
                            1 / divisor,
                            "2X2",
                            spacing,
                            f"handbook{cycle}+ot_decoder+{source}",
                        )
                    )
            # The handbook restricts enhanced-sensitivity 4x4 to DOUBLE,
            # one full-resource window per baseband, bandwidth <= 1000 MHz.
            if polarization == "DOUBLE" and bandwidth <= 1000:
                spacing = nominal / 1024
                for averaging, factor, source in RESPONSES:
                    rows.append(
                        QueueModeConfiguration(
                            f"C{cycle}_BLC_DOUBLE_{bandwidth:g}_4X4_R1_N{averaging}_H{factor:g}",
                            cycle,
                            "BLC",
                            polarization,
                            bandwidth,
                            spacing * factor,
                            "FDM",
                            averaging,
                            1.0,
                            "4X4",
                            spacing,
                            f"handbook{cycle}+ot_decoder+{source}",
                        )
                    )
        # Retain averaged TDM signatures too; 36.125 MHz is not FDM.
        spacing = 2000 / (256 / products)
        for averaging, factor, source in RESPONSES:
            rows.append(
                QueueModeConfiguration(
                    f"C{cycle}_BLC_{polarization}_1875_TDM_N{averaging}_H{factor:g}",
                    cycle,
                    "BLC",
                    polarization,
                    1875.0,
                    spacing * factor,
                    "TDM",
                    averaging,
                    1.0,
                    "2X2",
                    spacing,
                    f"handbook{cycle}+ot_decoder+{source}",
                )
            )
    return tuple(rows)
