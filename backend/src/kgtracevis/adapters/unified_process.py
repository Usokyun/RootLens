"""Complete process measurements to typed facts; no Root-KGD/RBC cause ranker."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from kgtracevis.schema.measured_reasoning import ProcessMeasurements
from kgtracevis.schema.unified_evidence import EvidenceFrame, Identifier, UnifiedModel


class ProcessReferenceAssets(UnifiedModel):
    reference_id: Identifier
    normal_uri: Identifier
    scaler_uri: Identifier
    shape: tuple[Annotated[int, Field(strict=True, gt=0)], Annotated[int, Field(strict=True, gt=0)]]
    columns: list[Identifier] = Field(min_length=1)

    @model_validator(mode="after")
    def column_axis(self):
        if len(set(self.columns)) != len(self.columns) or len(self.columns) != self.shape[1]:
            raise ValueError("normal reference needs a complete unambiguous column axis")
        return self


def process_frames(evidence):
    rows = [obs for obs in evidence.observations if obs.value_type == "process-measurements.v1"]
    if len(rows) != 1:
        raise ValueError("a process query requires one complete measured window")
    observation = rows[0]
    measured = ProcessMeasurements.model_validate(observation.value)
    extra = evidence.raw_evidence.extra
    scope, subject = "scope:window", "equipment"
    columns = [channel.channel for channel in measured.channels]
    window_uri = extra.get("window_array_path") or f"evidence://{evidence.case_id}/channels.samples"
    assets = [
        {
            "asset_id": "window",
            "kind": "typed_array",
            "uri": window_uri,
            "dtype": "float64",
            "shape": [measured.sample_end - measured.sample_start + 1, len(columns)],
            "columns": columns,
        }
    ]
    references, reference_id = [], None
    ref = extra.get("normal_reference_assets")
    if ref is not None:
        ref = ProcessReferenceAssets.model_validate(ref).model_dump(mode="json")
        if ref["reference_id"] != measured.reference_id or ref["columns"] != columns:
            raise ValueError(
                "normal reference identity or channel order differs from the measurements"
            )
        if ref["shape"] != [measured.normal_reference_rows, len(columns)]:
            raise ValueError("normal reference shape differs from the measured fit")
        reference_id = measured.reference_id
        assets.extend(
            [
                {
                    "asset_id": "normal",
                    "kind": "typed_array",
                    "uri": ref["normal_uri"],
                    "dtype": "float64",
                    "shape": ref["shape"],
                    "columns": columns,
                },
                {"asset_id": "scaler", "kind": "numeric_model", "uri": ref["scaler_uri"]},
            ]
        )
        references = [
            {
                "reference_id": reference_id,
                "kind": "normal_standardization",
                "normal_asset_id": "normal",
                "scaler_asset_id": "scaler",
            }
        ]
    procedures = [
        {
            "procedure_id": "normal-statistics",
            "kind": "measurement",
            "input_asset_ids": ["window", "scaler"] if references else ["window"],
            "reference_id": reference_id,
            "definition": "z=(x-normal_mean)/normal_scale; mean_z=mean(z); std_z=std(z,ddof=0); "
            "slope_z=OLS slope of z against zero-based sample index, unit 1/sample. "
            "Contribution is normalized squared PCA residual energy, not a root-cause probability.",
        }
    ]
    subjects = [
        {
            "subject_id": subject,
            "kind": "equipment",
            "external_namespace": "industrial.object",
            "external_id": evidence.object,
        }
    ]
    observations = []

    def add(identity, feature, number=None, *, boolean=None, unit="1", value=None, available=True):
        if value is None and available:
            value = (
                {"kind": "boolean", "boolean": boolean}
                if boolean is not None
                else {"kind": "number", "number": number, "unit": unit}
            )
        observations.append(
            {
                "obs_id": f"{observation.obs_id}:{identity}:{feature}",
                "subject_id": identity,
                "feature_id": feature,
                "value": value,
                "status": "observed" if available else "missing",
                "scope_id": scope,
                "procedure_id": "normal-statistics",
                "reference_id": reference_id,
                "dependency_group": "window",
                "raw_refs": ["window"],
            }
        )

    add(
        subject,
        "detection.anomaly_present",
        boolean=measured.residual_energy > measured.normal_energy_limit,
        available=bool(references),
    )
    add(subject, "residual.energy", measured.residual_energy)
    add(subject, "residual.normal_limit", measured.normal_energy_limit)
    for channel in measured.channels:
        identity = "variable:" + channel.channel
        subjects.append(
            {
                "subject_id": identity,
                "kind": "variable",
                "context_subject_id": subject,
                "external_namespace": "tep_braatz.channel",
                "external_id": channel.channel,
            }
        )
        for field, feature, unit in (
            ("mean_z", "statistics.mean_z", "1"),
            ("std_z", "statistics.std_z", "1"),
            ("slope_z", "statistics.slope_z", "1/sample"),
            ("contribution", "residual.contribution", "1"),
        ):
            add(identity, feature, getattr(channel, field), unit=unit)
        asset_id = "series:" + channel.channel
        assets.append(
            {
                "asset_id": asset_id,
                "kind": "typed_array",
                "uri": window_uri + "#column=" + channel.channel,
                "dtype": "float64",
                "shape": [len(channel.samples)],
            }
        )
        add(identity, "series.raw_values", value={"kind": "array_ref", "asset_id": asset_id})
    return [
        EvidenceFrame.model_validate(
            {
                "case_id": evidence.case_id + "/query/window",
                "source_dataset": evidence.dataset,
                "task": {
                    "target_role": "mechanism",
                    "context_subject_id": subject,
                    "focus_subject_ids": [subject],
                    "scope_id": scope,
                    "reference_id": reference_id,
                },
                "subjects": subjects,
                "scopes": [
                    {
                        "scope_id": scope,
                        "kind": "time_window",
                        "context_subject_id": subject,
                        "sample_start": measured.sample_start,
                        "sample_end": measured.sample_end,
                        "index_base": 1,
                        "end_inclusive": True,
                        "sampling_seconds": measured.sampling_interval_seconds,
                    }
                ],
                "assets": assets,
                "procedures": procedures,
                "references": references,
                "observations": observations,
            }
        )
    ]
