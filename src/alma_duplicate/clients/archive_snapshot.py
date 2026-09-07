"""Independent, read-only snapshots of scalar TAP rows.

Array-valued and arbitrary object cells are deliberately unsupported. A shallow
read-only wrapper around such cells would not protect the evidence it exposes.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

import numpy as np


def snapshot_archive_rows(
    rows: Iterable[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    """Copy each row, retaining immutable scalar types, order and duplicates.

    No normalization, masking, decoding or deduplication takes place here.
    Unsupported cells fail at the contract boundary rather than retaining mutable
    references. NumPy's canonical masked sentinel is retained as missing evidence.
    """

    snapshots = []
    for index, row in enumerate(rows):
        copied = {}
        for name, value in row.items():
            if type(name) is not str:
                raise TypeError(f"Archive row {index}: column names must be str")
            supported = (
                value is np.ma.masked
                or type(value) in (type(None), bool, int, float, complex, str, bytes)
                or (
                    isinstance(value, np.generic)
                    and type(value) is value.dtype.type
                    and value.dtype.kind in "biufcSUMm"
                )
            )
            if not supported:
                raise TypeError(
                    f"Archive row {index}, column {name!r}: unsupported cell "
                    f"type {type(value).__name__}; expected immutable scalar"
                )
            copied[name] = value
        snapshots.append(MappingProxyType(copied))
    return tuple(snapshots)
