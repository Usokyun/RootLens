"""Convert a bounded public WM811K table to JSONL without arbitrary pickle globals."""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from numpy._core.multiarray import _reconstruct, scalar
from numpy._core.numeric import _frombuffer
from pandas._libs.internals import _unpickle_block
from pandas.core.indexes.base import _new_Index
from pandas.core.internals.managers import BlockManager

ALLOWED = {
    ("pandas.core.frame", "DataFrame"): pd.DataFrame,
    ("pandas.core.internals.managers", "BlockManager"): BlockManager,
    ("pandas._libs.internals", "_unpickle_block"): _unpickle_block,
    ("numpy", "ndarray"): np.ndarray,
    ("numpy", "dtype"): np.dtype,
    ("builtins", "slice"): slice,
    ("pandas.core.indexes.base", "_new_Index"): _new_Index,
    ("pandas.core.indexes.base", "Index"): pd.Index,
    ("pandas.core.indexes.range", "RangeIndex"): pd.RangeIndex,
    ("pandas.core.indexes.numeric", "Int64Index"): pd.Index,
}
for prefix in ("numpy.core", "numpy._core"):
    ALLOWED[(prefix + ".multiarray", "_reconstruct")] = _reconstruct
    ALLOWED[(prefix + ".multiarray", "scalar")] = scalar
    ALLOWED[(prefix + ".numeric", "_frombuffer")] = _frombuffer


class DataOnlyUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in ALLOWED:
            raise pickle.UnpicklingError(f"not an allowed data constructor: {module}.{name}")
        return ALLOWED[(module, name)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--per-class", type=int, default=2)
    args = parser.parse_args()
    with args.input.open("rb") as handle:
        table = DataOnlyUnpickler(handle).load()
    if not isinstance(table, pd.DataFrame):
        raise ValueError("expected a WM811K dataframe")
    rows, counts = [], {}
    for index, row in table.iterrows():
        raw = row.get("failureType", row.get("label", "unknown"))
        flattened = np.asarray(raw).reshape(-1).tolist()
        label = str(flattened[0]) if flattened else "unlabeled"
        if counts.get(label, 0) >= args.per_class:
            continue
        wafer = np.asarray(row.get("waferMap", row.get("wafer_map")))
        if wafer.ndim != 2 or not np.isin(wafer, [0, 1, 2]).all():
            raise ValueError("expected native 0/1/2 die grid")
        rows.append({"wafer_id": str(index), "waferMap": wafer.tolist(), "failureType": label})
        counts[label] = counts.get(label, 0) + 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    print(json.dumps({"rows": len(rows), "native_label_counts": counts}))


if __name__ == "__main__":
    main()
