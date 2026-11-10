"""Raw Tennessee Eastman Process CSV record producer."""

from __future__ import annotations

import csv
import json
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from kgtracevis.producers.common import filter_forbidden_outputs

TEP_RBC_BACKEND = "tep-rbc"

FAULT_FREE_TRAINING_FILENAME = "TEP_FaultFree_Training.csv"
FAULTY_TRAINING_FILENAME = "TEP_Faulty_Training.csv"
DEFAULT_TEP_FAULTS = tuple(range(1, 22))
DEFAULT_TEP_WINDOW_SIZE = 100
DEFAULT_TEP_ROW_STRIDE = 25
DEFAULT_TEP_N_COMPONENTS = 18
DEFAULT_TEP_FAULT_FREE_MAX_ROWS: int | None = None
ID_COLUMNS = ("faultNumber", "simulationRun", "sample")
CHANNEL_PREFIXES = ("xmeas", "xmv")
ROOT_KGD_XMV_VARIABLE_IDS = {
    1: "variable:manipulated_variable_1_d_feed",
    2: "variable:manipulated_variable_2_e_feed",
    3: "variable:manipulated_variable_3_a_feed",
    4: "variable:manipulated_variable_4_a_and_c_feed",
    5: "variable:manipulated_variable_5_recycle",
    6: "variable:manipulated_variable_6_purge",
    7: "variable:manipulated_variable_7_separator",
    8: "variable:manipulated_variable_8_stripper",
    9: "variable:manipulated_variable_9_steam",
    10: "variable:manipulated_variable_10_reactor_coolant",
    11: "variable:manipulated_variable_11_condenser_coolant",
}


@dataclass(frozen=True)
class TepFaultFreeProfile:
    """Fault-free TEP profile used for residual contribution scoring."""

    variable_columns: tuple[str, ...]
    mean: np.ndarray
    scale: np.ndarray
    components: np.ndarray
    n_rows: int
    row_stride: int
    max_rows: int | None
    normal_energy_limit: float = 0.0
    reference_id: str = "normal-reference"


@dataclass(frozen=True)
class TepFaultWindow:
    """A fixed-size raw TEP faulty window."""

    fault_number: int
    simulation_run: int
    sample_start: int
    sample_end: int
    rows: np.ndarray


@dataclass(frozen=True)
class TepWindowContributions:
    """Residual contribution details for one TEP window."""

    channel_contributions: dict[str, float]
    residual_energy: float
    confidence: float


def build_tep_records(
    raw_data_dir: str | Path | None = None,
    *,
    fault_free_path: str | Path | None = None,
    faulty_path: str | Path | None = None,
    row_stride: int = DEFAULT_TEP_ROW_STRIDE,
    fault_free_max_rows: int | None = DEFAULT_TEP_FAULT_FREE_MAX_ROWS,
    window_size: int = DEFAULT_TEP_WINDOW_SIZE,
    faults: Sequence[int] | None = None,
    max_runs_per_fault: int = 3,
    max_cases: int | None = None,
    top_variables: int = 5,
    n_components: int | None = DEFAULT_TEP_N_COMPONENTS,
    profile_output_path: str | Path | None = None,
    window_start_sample: int = 1,
    sampling_interval_seconds: float = 180,
    fault_start_sample: int | None = None,
) -> list[dict[str, Any]]:
    """Build adapter-ready TEP records from raw fault-free and faulty CSV files."""
    if raw_data_dir is None and (fault_free_path is None or faulty_path is None):
        raw_data_dir = Path("data/raw/tep")
    data_dir = Path(raw_data_dir) if raw_data_dir is not None else None
    fault_free_csv = _resolve_tep_csv_path(
        explicit_path=fault_free_path,
        raw_data_dir=data_dir,
        filename=FAULT_FREE_TRAINING_FILENAME,
    )
    faulty_csv = _resolve_tep_csv_path(
        explicit_path=faulty_path,
        raw_data_dir=data_dir,
        filename=FAULTY_TRAINING_FILENAME,
    )
    _validate_positive("row_stride", row_stride)
    _validate_positive("window_size", window_size)
    _validate_positive("max_runs_per_fault", max_runs_per_fault)
    _validate_positive("top_variables", top_variables)
    if max_cases is not None and max_cases < 0:
        raise ValueError("max_cases must be non-negative")

    variable_columns = _variable_columns(fault_free_csv)
    _validate_faulty_columns(faulty_csv, variable_columns)
    profile = fit_tep_fault_free_profile(
        fault_free_csv,
        variable_columns=variable_columns,
        row_stride=row_stride,
        max_rows=fault_free_max_rows,
        n_components=n_components,
    )
    if profile_output_path is not None:
        _write_profile(profile, Path(profile_output_path))

    selected_faults = tuple(int(fault) for fault in (faults or DEFAULT_TEP_FAULTS))
    windows = collect_tep_fault_windows(
        faulty_csv,
        variable_columns=profile.variable_columns,
        faults=selected_faults,
        window_size=window_size,
        max_runs_per_fault=max_runs_per_fault,
        max_cases=max_cases,
        window_start_sample=window_start_sample,
    )
    return [
        _record_from_window(
            window,
            contribution=compute_tep_window_contributions(profile, window),
            faulty_path=faulty_csv,
            profile=profile,
            top_variables=top_variables,
            sampling_interval_seconds=sampling_interval_seconds,
            fault_start_sample=fault_start_sample,
        )
        for window in windows
    ]


def build_tep_dat_records(
    normal_path,
    sequence_path,
    *,
    output_dir,
    windows,
    sampling_interval_seconds=180.0,
    fault_start_sample=None,
    n_components=18,
):
    """Braatz 52-channel reference .dat input; explicit one-based inclusive windows.

    This new route fits a matched normal scaler/PCA and does not use legacy memory
    templates or fault labels. The legacy training-CSV entry point is unchanged.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    def matrix(path):
        values = np.loadtxt(path, dtype=float)
        if values.ndim == 2 and values.shape[0] == 52 and values.shape[1] != 52:
            values = values.T
        if values.ndim != 2 or values.shape[1] != 52 or not np.isfinite(values).all():
            raise ValueError("Braatz .dat requires 52 finite channels: XMEAS1..41 then XMV1..11")
        return values

    normal, sequence = matrix(normal_path), matrix(sequence_path)
    columns = [f"xmeas_{i}" for i in range(1, 42)] + [f"xmv_{i}" for i in range(1, 12)]
    normal_csv = output / "normal_reference.csv"
    with normal_csv.open("w") as f:
        f.write(",".join(columns) + "\n")
        np.savetxt(f, normal, delimiter=",")
    reference = fit_tep_fault_free_profile(normal_csv, row_stride=1, n_components=n_components)
    # This new producer publishes a distinct fitted-reference identity. The
    # historical CSV producer's reference/entry contract remains unchanged.
    reference = replace(reference, reference_id="normal-fit:" + uuid.uuid4().hex)
    _write_profile(reference, output / "normal_reference_profile.json")
    records = []
    for start, end in windows:
        if start < 1 or end < start or end > len(sequence):
            raise ValueError("process window is outside the sequence")
        window = TepFaultWindow(0, 1, start, end, sequence[start - 1 : end])
        record = _record_from_window(
            window,
            contribution=compute_tep_window_contributions(reference, window),
            faulty_path=Path(sequence_path),
            profile=reference,
            top_variables=6,
            sampling_interval_seconds=sampling_interval_seconds,
            fault_start_sample=fault_start_sample,
        )
        record.update(
            case_id=f"process_window_{start}_{end}",
            anomaly_type="multivariate_deviation",
            description=(
                f"Process samples {start}–{end}; compared with a matched fault-free reference."
            ),
        )
        for key in ("fault_number", "fault_id", "scenario_id"):
            record.pop(key, None)
        record["extra"]["normal_reference_profile_path"] = str(
            output / "normal_reference_profile.json"
        )
        window_path = output / f"window_{start}_{end}.npy"
        np.save(window_path, window.rows, allow_pickle=False)
        record["extra"]["window_array_path"] = str(window_path)
        record["extra"]["normal_reference_assets"] = {
            "reference_id": reference.reference_id,
            "normal_uri": str(normal_csv),
            "scaler_uri": str(output / "normal_reference_profile.json"),
            "shape": [reference.n_rows, len(columns)],
            "columns": columns,
        }
        records.append(record)
    return records


def fit_tep_fault_free_profile(
    fault_free_path: str | Path,
    *,
    variable_columns: Sequence[str] | None = None,
    row_stride: int = DEFAULT_TEP_ROW_STRIDE,
    max_rows: int | None = None,
    n_components: int | None = DEFAULT_TEP_N_COMPONENTS,
) -> TepFaultFreeProfile:
    """Fit a compact fault-free TEP reconstruction profile from raw CSV rows."""
    _validate_positive("row_stride", row_stride)
    if max_rows is not None and max_rows <= 0:
        raise ValueError("max_rows must be positive when provided")

    path = Path(fault_free_path)
    columns = tuple(variable_columns or _variable_columns(path))
    samples: list[list[float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_columns(path, reader.fieldnames, columns)
        for index, row in enumerate(reader):
            if index % row_stride != 0:
                continue
            samples.append(_row_values(row, columns))
            if max_rows is not None and len(samples) >= max_rows:
                break
    if len(samples) < 2:
        raise ValueError(f"{path} must provide at least two sampled fault-free rows")

    matrix = np.asarray(samples, dtype=float)
    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0, ddof=1)
    scale = np.where(scale > 1e-12, scale, 1.0)
    standardized = (matrix - mean) / scale
    component_count = _component_count(
        requested=n_components,
        column_count=len(columns),
        row_count=len(samples),
    )
    components = _principal_components(standardized, component_count)
    residual = standardized - (standardized @ components) @ components.T
    energy_limit = float(np.quantile(np.sum(residual**2, axis=1), 0.99))
    return TepFaultFreeProfile(
        variable_columns=columns,
        mean=mean,
        scale=scale,
        components=components,
        n_rows=len(samples),
        row_stride=row_stride,
        max_rows=max_rows,
        normal_energy_limit=energy_limit,
        reference_id=f"{path.name}:rows={len(samples)}:stride={row_stride}:pca={component_count}",
    )


def collect_tep_fault_windows(
    faulty_path: str | Path,
    *,
    variable_columns: Sequence[str],
    faults: Sequence[int] = DEFAULT_TEP_FAULTS,
    window_size: int = 100,
    max_runs_per_fault: int = 3,
    max_cases: int | None = None,
    window_start_sample: int = 1,
) -> list[TepFaultWindow]:
    """Collect fixed-size faulty windows grouped by TEP fault and simulation run."""
    _validate_positive("window_size", window_size)
    _validate_positive("max_runs_per_fault", max_runs_per_fault)
    if max_cases is not None and max_cases < 0:
        raise ValueError("max_cases must be non-negative")

    path = Path(faulty_path)
    target_faults = {int(fault) for fault in faults}
    if not target_faults:
        return []

    active_rows: dict[tuple[int, int], list[list[float]]] = defaultdict(list)
    sample_ranges: dict[tuple[int, int], list[int]] = {}
    completed_runs: dict[int, set[int]] = defaultdict(set)
    windows: list[TepFaultWindow] = []

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_columns(path, reader.fieldnames, (*ID_COLUMNS, *variable_columns))
        for row in reader:
            if _int_cell(row, "sample") < window_start_sample:
                continue
            fault_number = _int_cell(row, "faultNumber")
            if fault_number not in target_faults:
                continue
            simulation_run = _int_cell(row, "simulationRun")
            if simulation_run in completed_runs[fault_number]:
                continue
            if len(completed_runs[fault_number]) >= max_runs_per_fault:
                continue

            key = (fault_number, simulation_run)
            rows = active_rows[key]
            if not rows:
                sample_ranges[key] = [_int_cell(row, "sample"), _int_cell(row, "sample")]
            else:
                if _int_cell(row, "sample") != sample_ranges[key][1] + 1:
                    raise ValueError(
                        "TEP windows require contiguous sample indices within each run"
                    )
                sample_ranges[key][1] = _int_cell(row, "sample")
            rows.append(_row_values(row, variable_columns))
            if len(rows) < window_size:
                continue

            completed_runs[fault_number].add(simulation_run)
            sample_start, sample_end = sample_ranges[key]
            windows.append(
                TepFaultWindow(
                    fault_number=fault_number,
                    simulation_run=simulation_run,
                    sample_start=sample_start,
                    sample_end=sample_end,
                    rows=np.asarray(rows, dtype=float),
                )
            )
            del active_rows[key]
            del sample_ranges[key]
            if max_cases is not None and len(windows) >= max_cases:
                break
            if _all_requested_runs_collected(
                completed_runs,
                target_faults=target_faults,
                max_runs_per_fault=max_runs_per_fault,
            ):
                break
    return windows


def compute_tep_window_contributions(
    profile: TepFaultFreeProfile,
    window: TepFaultWindow,
) -> TepWindowContributions:
    """Compute normalized residual contribution mass for one faulty TEP window."""
    standardized = (window.rows - profile.mean) / profile.scale
    if profile.components.size:
        scores = standardized @ profile.components
        reconstructed = scores @ profile.components.T
        residual = standardized - reconstructed
    else:
        residual = standardized

    residual_squared = np.mean(np.square(residual), axis=0)
    total = float(residual_squared.sum())
    if total <= 1e-12:
        fallback = np.mean(np.abs(standardized), axis=0)
        total = float(fallback.sum())
        residual_squared = fallback
    if total <= 1e-12:
        contributions = np.full(len(profile.variable_columns), 1.0 / len(profile.variable_columns))
        residual_energy = 0.0
    else:
        contributions = residual_squared / total
        residual_energy = float(np.mean(np.sum(np.square(residual), axis=1)))

    return TepWindowContributions(
        channel_contributions={
            _canonical_channel_name(column): round(float(value), 8)
            for column, value in zip(profile.variable_columns, contributions, strict=True)
        },
        residual_energy=residual_energy,
        confidence=_unit_interval(residual_energy / (residual_energy + 1.0)),
    )


def _record_from_window(
    window: TepFaultWindow,
    *,
    contribution: TepWindowContributions,
    faulty_path: Path,
    profile: TepFaultFreeProfile,
    top_variables: int,
    sampling_interval_seconds: float = 180,
    fault_start_sample: int | None = None,
) -> dict[str, Any]:
    ranked = sorted(
        contribution.channel_contributions.items(),
        key=lambda item: (-item[1], item[0]),
    )
    top = ranked[:top_variables]
    variables = [name for name, _value in top]
    variable_contributions = {name: value for name, value in top}
    from kgtracevis.schema.measured_reasoning import ProcessChannel, ProcessMeasurements

    standardized = (window.rows - profile.mean) / profile.scale
    measured = ProcessMeasurements(
        reference_id=profile.reference_id,
        sample_start=window.sample_start,
        sample_end=window.sample_end,
        sampling_interval_seconds=sampling_interval_seconds,
        fault_start_sample=fault_start_sample,
        normal_reference_rows=profile.n_rows,
        residual_energy=contribution.residual_energy,
        normal_energy_limit=profile.normal_energy_limit,
        channels=[
            ProcessChannel(
                channel=_canonical_channel_name(column).lower(),
                mean_z=float(standardized[:, i].mean()),
                std_z=float(standardized[:, i].std()),
                slope_z=float(np.polyfit(np.arange(len(window.rows)), standardized[:, i], 1)[0]),
                contribution=contribution.channel_contributions[_canonical_channel_name(column)],
                samples=window.rows[:, i].tolist(),
            )
            for i, column in enumerate(profile.variable_columns)
        ],
    )
    case_id = (
        f"tep_fault_{window.fault_number:02d}_run_{window.simulation_run:03d}"
        f"_samples_{window.sample_start:06d}_{window.sample_end:06d}"
    )
    record = {
        "dataset": "tep",
        "source": "tep_csv_rbc",
        "adapter": "tep",
        "case_id": case_id,
        "scenario_id": case_id,
        "object": "Tennessee Eastman Process",
        "anomaly_type": f"fault_{window.fault_number:02d}",
        "location": "process",
        "morphology": "multivariate_residual_shift",
        "severity": contribution.confidence,
        "confidence": contribution.confidence,
        "variables": variables,
        "variable_contributions": variable_contributions,
        "description": (
            f"TEP fault {window.fault_number} simulation run {window.simulation_run} "
            f"samples {window.sample_start}-{window.sample_end} residual contribution window."
        ),
        "fault_number": window.fault_number,
        "fault_id": window.fault_number,
        "simulation_run": window.simulation_run,
        "simulation_id": window.simulation_run,
        "run_id": window.simulation_run,
        "sample_start": window.sample_start,
        "sample_end": window.sample_end,
        "window": f"{window.sample_start}:{window.sample_end}",
        "window_start": window.sample_start,
        "window_end": window.sample_end,
        "window_size": int(window.rows.shape[0]),
        "raw_data_path": str(faulty_path),
        "detector": {
            "name": "tep_residual_contribution",
            "backend": TEP_RBC_BACKEND,
            "profile_rows": profile.n_rows,
            "profile_row_stride": profile.row_stride,
            "profile_max_rows": profile.max_rows,
            "n_components": int(profile.components.shape[1]) if profile.components.ndim == 2 else 0,
            "residual_energy": round(contribution.residual_energy, 8),
            "produces_root_cause": False,
        },
        "extra": {
            "process_measurements": measured.model_dump(mode="json"),
            "channel_contributions": contribution.channel_contributions,
            "graph_contributions": _root_kgd_graph_contributions(
                contribution.channel_contributions
            ),
            "root_kgd_dynamic_features": _root_kgd_dynamic_features(profile, window),
            "top_channels": variables,
            "source_columns": list(profile.variable_columns),
        },
    }
    return filter_forbidden_outputs(record)


def _root_kgd_graph_contributions(
    channel_contributions: Mapping[str, float],
) -> dict[str, float]:
    graph_contributions: dict[str, float] = {}
    for channel_name, value in channel_contributions.items():
        variable_id = _root_kgd_variable_id(channel_name)
        if variable_id is not None:
            graph_contributions[variable_id] = round(float(value), 8)
    return graph_contributions


def _root_kgd_dynamic_features(
    profile: TepFaultFreeProfile,
    window: TepFaultWindow,
) -> dict[str, Any]:
    standardized = (window.rows - profile.mean) / profile.scale
    features: dict[str, float] = {}
    for index, column in enumerate(profile.variable_columns):
        channel_id = _root_kgd_channel_id(column)
        if channel_id is None:
            continue
        values = standardized[:, index]
        mean_z = float(np.mean(values))
        slope_z = float((values[-1] - values[0]) / max(1, len(values) - 1))
        deltas = np.diff(values)
        oscillation = float(np.mean(np.abs(deltas))) if deltas.size else 0.0
        std_z = float(np.std(values))
        features[f"{channel_id}__mean"] = round(mean_z, 8)
        features[f"{channel_id}__slope"] = round(slope_z, 8)
        features[f"{channel_id}__osc"] = round(oscillation, 8)
        features[f"{channel_id}__std"] = round(std_z, 8)
    return {
        "feature_version": "scenario_dynamic_v1",
        "features": features,
        "top_dynamic_features": _top_dynamic_features(features),
    }


def _top_dynamic_features(features: Mapping[str, float], limit: int = 6) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature_id, value in sorted(
        features.items(),
        key=lambda item: (-abs(float(item[1])), item[0]),
    ):
        if abs(float(value)) <= 1e-9:
            continue
        channel_id, _, statistic = feature_id.partition("__")
        rows.append(
            {
                "feature_id": feature_id,
                "channel_id": channel_id,
                "statistic": statistic,
                "value": round(float(value), 8),
                "magnitude": round(abs(float(value)), 8),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _root_kgd_variable_id(channel_name: str) -> str | None:
    parts = _channel_parts(channel_name)
    if parts is None:
        return None
    prefix, number = parts
    if prefix == "xmeas":
        return f"variable:xmeas_{number}"
    if prefix == "xmv":
        return ROOT_KGD_XMV_VARIABLE_IDS.get(number)
    return None


def _root_kgd_channel_id(channel_name: str) -> str | None:
    parts = _channel_parts(channel_name)
    if parts is None:
        return None
    prefix, number = parts
    return f"{prefix}_{number}"


def _resolve_tep_csv_path(
    *,
    explicit_path: str | Path | None,
    raw_data_dir: Path | None,
    filename: str,
) -> Path:
    path = (
        Path(explicit_path)
        if explicit_path is not None
        else (raw_data_dir / filename if raw_data_dir else None)
    )
    if path is None:
        raise ValueError(f"{filename} path is required")
    if not path.is_file():
        raise FileNotFoundError(f"TEP CSV not found: {path}")
    return path


def _variable_columns(path: Path) -> tuple[str, ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{path} is empty") from exc
    columns = tuple(
        sorted(
            (name for name in header if _is_channel_column(name)),
            key=_channel_sort_key,
        )
    )
    if not columns:
        raise ValueError(f"{path} does not contain xmeas/xmv variable columns")
    return columns


def _validate_faulty_columns(path: Path, variable_columns: Sequence[str]) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_columns(path, reader.fieldnames, (*ID_COLUMNS, *variable_columns))


def _require_columns(path: Path, fieldnames: Sequence[str] | None, columns: Iterable[str]) -> None:
    if fieldnames is None:
        raise ValueError(f"{path} is missing a CSV header")
    missing = [column for column in columns if column not in fieldnames]
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")


def _is_channel_column(name: str) -> bool:
    return _channel_parts(name) is not None


def _channel_sort_key(name: str) -> tuple[int, int, str]:
    lower = name.strip().lower()
    parts = _channel_parts(lower)
    if parts is None:
        return (2, 10**6, lower)
    prefix, number = parts
    prefix_rank = 0 if prefix == "xmeas" else 1
    return (prefix_rank, number, lower)


def _canonical_channel_name(name: str) -> str:
    parts = _channel_parts(name)
    if parts is None:
        return name.strip().upper()
    prefix, number = parts
    return f"{prefix.upper()}_{number}"


def _channel_parts(name: str) -> tuple[str, int] | None:
    lower = name.strip().lower()
    for prefix in CHANNEL_PREFIXES:
        if not lower.startswith(prefix):
            continue
        suffix = lower.removeprefix(prefix)
        if suffix.startswith("_"):
            suffix = suffix[1:]
        if suffix.isdigit():
            return prefix, int(suffix)
    return None


def _row_values(row: dict[str, str], columns: Sequence[str]) -> list[float]:
    return [_float_cell(row, column) for column in columns]


def _float_cell(row: dict[str, str], column: str) -> float:
    try:
        return float(row[column])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric value for {column}: {row.get(column)!r}") from exc


def _int_cell(row: dict[str, str], column: str) -> int:
    try:
        return int(float(row[column]))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer value for {column}: {row.get(column)!r}") from exc


def _component_count(
    *,
    requested: int | None,
    column_count: int,
    row_count: int,
) -> int:
    if requested is not None and requested < 0:
        raise ValueError("n_components must be non-negative")
    max_components = max(0, min(column_count - 1, row_count - 1))
    if requested is None:
        return min(6, max_components)
    return min(requested, max_components)


def _principal_components(standardized: np.ndarray, component_count: int) -> np.ndarray:
    if component_count <= 0:
        return np.empty((standardized.shape[1], 0), dtype=float)
    covariance = np.cov(standardized, rowvar=False)
    covariance = np.atleast_2d(covariance)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    return eigenvectors[:, order[:component_count]]


def _all_requested_runs_collected(
    completed_runs: dict[int, set[int]],
    *,
    target_faults: set[int],
    max_runs_per_fault: int,
) -> bool:
    return all(len(completed_runs[fault]) >= max_runs_per_fault for fault in target_faults)


def _unit_interval(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 8)


def _validate_positive(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _write_profile(profile: TepFaultFreeProfile, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "variable_columns": list(profile.variable_columns),
        "mean": profile.mean.tolist(),
        "scale": profile.scale.tolist(),
        "components": profile.components.tolist(),
        "n_rows": profile.n_rows,
        "row_stride": profile.row_stride,
        "max_rows": profile.max_rows,
        "normal_energy_limit": profile.normal_energy_limit,
        "reference_id": profile.reference_id,
    }
    output_path.write_text(
        json.dumps(filter_forbidden_outputs(payload), indent=2, sort_keys=False),
        encoding="utf-8",
    )
