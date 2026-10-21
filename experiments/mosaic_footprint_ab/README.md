# Archive Mosaic Footprint Comparison

A standalone geometric comparison between an ALMA Archive `s_region` polygon and the union of circular beams centred on observed science fields. The result is diagnostic only; it does not assess whether an observation is a duplicate.

## Data

- Project: `2021.2.00176.S`, target `SPT0303-59`
- Member: `uid://A001/X15aa/Xe5`
- ASDM: `uid://A002/Xfb8480/X4f37` (one execution)
- Array: 7m, observation frequency from TAP: approximately 350.985 GHz
- Method A: 42-vertex `Polygon ICRS` from the original TAP VOTable
- Method B: 19 `OBSERVE_TARGET#ON_SOURCE` fields (FIELD_ID 3–21), derived from the pipeline weblog `listobs`; calibration field 2 is excluded

Original snapshots are in `data/`. The source `listobs` is retained to trace the science-only field selection. The summaries record hashes of the TAP and pointing CSV inputs. They are not complete acquisition manifests: listobs acquisition provenance and the derivation chain still need to be documented.

## Run

From the repository root:

```sh
python -m unittest discover -s experiments/mosaic_footprint_ab -p 'test_*.py' -v
audit_out=$(mktemp -d /tmp/mosaic-ab-XXXXXX)
python experiments/mosaic_footprint_ab/compare.py --output "$audit_out/7m"
python experiments/mosaic_footprint_ab/compare_archive.py \
  --tap experiments/mosaic_footprint_ab/data/ngc5248_12m_tap.xml \
  --fields experiments/mosaic_footprint_ab/data/ngc5248_12m_pointings.csv \
  --expected-array 12m \
  --output-dir "$audit_out/12m"
```

The comparison uses Python 3.11+ standard library only. An optional diagnostic chart requires the `matplotlib` development dependency:

```sh
python experiments/mosaic_footprint_ab/plot.py
```

Use `--step-arcsec 0.5 --coefficients 1.13` for a finer raster check. The commands above write to a new temporary directory. Script defaults and the plotting command can overwrite existing results; preserve captured outputs and use a separate output location when rerunning.

## Initial results

| Assumed HPBW coefficient | Beam half-power radius | Sampled footprint IoU (1 arcsec grid) | Polygon-only cells | Beam-only cells |
|---|---:|---:|---:|---:|
| 1.13 | 14.220 arcsec | 0.9892 | 27 | 34 |
| 1.15 | 14.472 arcsec | 0.9822 | 3 | 99 |
| 1.17 | 14.724 arcsec | 0.9710 | 0 | 168 |

At 0.5 arcsec grid spacing and coefficient 1.13, the sampled IoU is approximately 0.9905. The 42 polygon vertices lie 14.501–14.510 arcsec from their nearest observed science-field centres; this is evidence of related geometry, not proof of the `s_region` response definition. Boundary probes detect disagreement even at the baseline coefficient.

## Independent 12m sample

NGC5248, project `2019.1.01718.S`, ASDM `uid://A002/Xeaae1d/X1a2`, has 11 science fields (FIELD_ID 4–14) and a 33-vertex TAP polygon. At 1 arcsec sampling, coefficient 1.13 gives IoU approximately 0.9538, with 0 polygon-only and 58 beam-only cells. These are local diagnostic results for one ASDM, not a complete Member assessment.

`extract_science_fields.py` locates a unique MeasurementSet header and checks its exact basename against the TAP ASDM. Regression tests cover the supplied Markdown-wrapped 7m listobs, the plain 12m listobs, and missing, mismatched or ambiguous headers. Both samples can now be extracted from their local listobs snapshots. This verifies local parsing, not remote acquisition provenance or Member completeness.

To reproduce extraction without overwriting the captured CSVs:

```sh
extract_out=$(mktemp -d /tmp/mosaic-fields-XXXXXX)
python experiments/mosaic_footprint_ab/extract_science_fields.py \
  --listobs experiments/mosaic_footprint_ab/data/source_listobs.md \
  --tap experiments/mosaic_footprint_ab/data/case_E_tap.xml \
  --array 7m --output "$extract_out/7m.csv"
python experiments/mosaic_footprint_ab/extract_science_fields.py \
  --listobs experiments/mosaic_footprint_ab/data/ngc5248_12m_listobs.txt \
  --tap experiments/mosaic_footprint_ab/data/ngc5248_12m_tap.xml \
  --array 12m --output "$extract_out/12m.csv"
```

The array argument is supplied by the caller; extraction does not independently validate dish diameters. See `data/local_fixture_inventory.json` for local file hashes and explicit acquisition-evidence limitations.

## Method and limitations

- Circular half-power radius: `coefficient * (speed of light / frequency) / dish diameter / 2`, in radians. Coefficients 1.13, 1.15 and 1.17 are *sensitivity assumptions*, not individually certified policy rules.
- Great-circle separation is used for beam membership. STC-S polygon membership uses straight edges in a local azimuthal-equidistant projection, adequate for exploring this small footprint but not a general exact spherical-region parser.
- Raster IoU estimates geometric overlap at the stated sampling resolution; it is not an exact area integral or a validation of the Archive metadata's physical threshold. The CSV outputs identify disagreements and test polygon-edge offsets of 0.1, 0.5 and 1.0 arcsec.
- The two samples each cover one ASDM, not the completeness of their Members or all ALMA observing modes. They do not test TP, per-SPW beam variation, mosaic combined response, candidate search completeness, or numerical equality at formal policy boundaries.
- **A high IoU does not imply identical classification of proposed pointings.** Near a strict >50% threshold, even one boundary disagreement can change the position result.

## Next gate

Check the Archive documentation or ALMA/ARC expertise for the semantics of the published `s_region`. The independent 12m sample is now included; further sampling should target specific unresolved implementation requirements. Only use the polygon as an authoritative half-power proxy after the definition and boundary behaviour have been validated. Until then, retain actual science fields as the candidate-side reference evidence.
