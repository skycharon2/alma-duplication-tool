# M33 overlapping Archive SPWs

`m33.xml` is a narrow, read-only TAP response retrieved on 2026-11-18 from
`https://almascience.eso.org/tap/sync` using ADQL and VOTable output:

```sql
SELECT obs_id,frequency,bandwidth,em_min,em_max,frequency_support
FROM ivoa.obscore
WHERE member_ous_uid='uid://A001/X3833/X1121'
AND asdm_uid='uid://A002/X13c84cf/X232f9'
AND target_name='M33'
```

The response supplies GHz frequency, Hz nominal bandwidth and metre wavelength
bounds. It reproduces the overlapping-interval association issue. It is not a
complete source-retrieval fixture or independent duplication verdict. Integration
tests combine these spectral fields with synthetic non-spectral metadata.

Expected support components, verified against both converted wavelength edges:
SPW 25 -> 3; SPW 17 -> 1; SPW 27 -> 4; SPW 19 -> 2.
Nominal bandwidth alone is deliberately not used to recover these edges.

SHA-256: `f00377c7ec0791f0c1ade722f34238a5283725defce82c75d9488a471c279d94`.
