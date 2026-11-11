"""Data constructors for the integrity-pinned WM811K release table only."""

from __future__ import annotations

import pickle

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
