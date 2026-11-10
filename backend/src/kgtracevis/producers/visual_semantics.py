"""Opt-in ROI semantics through a configured vision-capable OpenAI-compatible service."""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from kgtracevis.schema.visual_reasoning import VisualRegion
from kgtracevis.source_kg_compiler.llm import load_source_kg_env, safe_json_parse


class ROISemanticPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concept_ids: list[str] = Field(max_length=4)
    description: str = Field(max_length=1000)
    observation_state: Literal["defect", "normal", "uncertain"]


class ROISemanticServiceError(RuntimeError):
    """The requested external inference failed; no substitute diagnosis was made."""


class OpenAICompatibleROISemantics:
    """One bounded call per selected ROI; model output cannot create graph concepts."""

    def __init__(self, *, client: Any = None, model: str | None = None, max_regions: int = 3):
        load_source_kg_env()
        self.model = (
            model
            or os.environ.get("KGTRACEVIS_VISION_MODEL")
            or os.environ.get("OPENAI_MODEL")
            or os.environ.get("DEEPSEEK_MODEL")
        )
        if not self.model:
            raise ValueError("ROI 识别需要配置 KGTRACEVIS_VISION_MODEL（支持图像的模型）。")
        if client is None:
            key = (
                os.environ.get("KGTRACEVIS_VISION_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("DEEPSEEK_API_KEY")
            )
            if not key:
                raise ValueError("ROI 识别需要配置视觉服务 API key。")
            from openai import OpenAI

            client = OpenAI(
                api_key=key,
                base_url=os.environ.get("KGTRACEVIS_VISION_BASE_URL")
                or os.environ.get("OPENAI_BASE_URL")
                or os.environ.get("DEEPSEEK_BASE_URL"),
                max_retries=0,
                timeout=60,
            )
        if max_regions < 1:
            raise ValueError("max_regions must be positive")
        self.client = client
        self.max_regions = max_regions
        self.calls = 0
        self.tokens = 0

    def annotate(
        self,
        image_path: Path,
        regions: list[VisualRegion],
        *,
        object_name: str,
        concepts: list[dict[str, str]],
        output_dir: Path,
        normal_reference_path: Path | None = None,
    ) -> list[VisualRegion]:
        """Send neutral-named crops, not path names, native labels, or cause hypotheses."""
        allowed_ids = {c["concept_id"] for c in concepts}
        if not allowed_ids:
            raise ValueError("当前工作图没有可用于 ROI 识别的缺陷概念。")
        chosen = {
            r.region_id
            for r in sorted(
                regions,
                key=lambda r: (-(r.area_ratio or 0), r.region_id),
            )[: self.max_regions]
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        annotated = []
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            context = image.copy()
            context.thumbnail((768, 768))
            context_buffer = io.BytesIO()
            context.save(context_buffer, format="PNG")
            context_url = (
                "data:image/png;base64," + base64.b64encode(context_buffer.getvalue()).decode()
            )
            normal_url = None
            if normal_reference_path is not None:
                with Image.open(normal_reference_path) as normal:
                    normal = normal.convert("RGB")
                    normal.thumbnail((768, 768))
                    buf = io.BytesIO()
                    normal.save(buf, format="PNG")
                    normal_url = (
                        "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
                    )
            for region in regions:
                if region.region_id not in chosen:
                    annotated.append(
                        region.model_copy(
                            update={
                                "semantic_status": "not_evaluated_budget",
                            }
                        )
                    )
                    continue
                bbox = region.image_bbox_xyxy
                if bbox is None:
                    annotated.append(region.model_copy(update={"semantic_status": "unaligned"}))
                    continue
                x1, y1, x2, y2 = bbox
                padding = max(
                    8,
                    round(max(x2 - x1, y2 - y1) * 0.15),
                    round(min(image.width, image.height) * 0.12),
                )
                crop_bbox = (
                    max(0, int(x1) - padding),
                    max(0, int(y1) - padding),
                    min(image.width, int(x2 + 1) + padding),
                    min(image.height, int(y2 + 1) + padding),
                )
                crop = image.crop(crop_bbox)
                crop.thumbnail((768, 768))
                # Region IDs are caller data, not paths.
                roi_path = output_dir / f"roi_{len(annotated) + 1}.png"
                crop.save(roi_path)
                buffer = io.BytesIO()
                crop.save(buffer, format="PNG")
                url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
                target_box = [
                    round(x1 - crop_bbox[0]),
                    round(y1 - crop_bbox[1]),
                    round(x2 - crop_bbox[0]),
                    round(y2 - crop_bbox[1]),
                ]
                prompt = (
                    f"Inspect the proposed anomaly on object {object_name}. Image 1 is the "
                    "whole source image for object/background context. Image 2 is a crop. "
                    f"The anomaly's xyxy box in image 2 is {target_box}. "
                    "Inspect that box specifically; it may be a background mark. "
                    "First check whether that region is physically on the named object. "
                    "Select only visibly supported "
                    "defect concepts from this JSON list. Return JSON with concept_ids (list) "
                    "and description (visible appearance only), plus observation_state "
                    "(defect/normal/uncertain). Use an empty list if normal or uncertain. "
                    "Only defects on the named object count; "
                    "background marks are not object defects. "
                    "Do not infer factory causes, machinery, or unseen events.\n"
                    'Exact response shape: {"concept_ids": [], "description": "...", '
                    '"observation_state": "uncertain"}. No other fields.\n'
                    + json.dumps(concepts, ensure_ascii=False)
                )
                if normal_url:
                    prompt += (
                        "\nImage 3 is a separately supplied normal reference "
                        "of the SAME object category. "
                        "Compare visible structure with this reference; "
                        "do not call normal material a defect. "
                        "A missing/broken part is a visible geometric change, "
                        "not necessarily a colored mark."
                    )
                content = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": context_url, "detail": "high"}},
                    {"type": "image_url", "image_url": {"url": url, "detail": "high"}},
                ]
                if normal_url:
                    content.append(
                        {"type": "image_url", "image_url": {"url": normal_url, "detail": "high"}}
                    )
                if os.environ.get("KGTRACEVIS_VISION_API", "chat_completions") == "responses":
                    response = self._request(
                        self.client.responses.create,
                        model=self.model,
                        store=False,
                        max_output_tokens=600,
                        text={"format": {"type": "json_object"}},
                        input=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "input_text", "text": prompt},
                                    {
                                        "type": "input_image",
                                        "image_url": context_url,
                                        "detail": "high",
                                    },
                                    {"type": "input_image", "image_url": url, "detail": "high"},
                                    *(
                                        [
                                            {
                                                "type": "input_image",
                                                "image_url": normal_url,
                                                "detail": "high",
                                            }
                                        ]
                                        if normal_url
                                        else []
                                    ),
                                ],
                            }
                        ],
                    )
                    if response.status != "completed":
                        raise ValueError(f"ROI 识别未完成：{response.status}")
                    text = response.output_text
                else:
                    response = self._request(
                        self.client.chat.completions.create,
                        model=self.model,
                        messages=[{"role": "user", "content": content}],
                        response_format={"type": "json_object"},
                        max_tokens=600,
                        **(
                            {"extra_body": {"thinking": {"type": "disabled"}}}
                            if "deepseek" in self.model.lower()
                            else {}
                        ),
                    )
                    if response.choices[0].finish_reason != "stop":
                        raise ValueError("ROI 识别输出未完整结束。")
                    text = response.choices[0].message.content
                self.calls += 1
                self.tokens += int(
                    getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
                )
                roi_path.with_suffix(".semantics.json").write_text(
                    json.dumps(
                        {
                            "model": self.model,
                            "response": text,
                            "calls_so_far": self.calls,
                            "tokens_so_far": self.tokens,
                            "normal_reference_path": str(normal_reference_path)
                            if normal_reference_path
                            else None,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                payload = safe_json_parse(text or "")
                # Observed provider output sometimes echoes its JSON transport format tag.
                # Only this exact transport tag is accepted; semantic fields stay closed.
                if isinstance(payload, dict) and payload.get("type") == "json_object":
                    payload = {key: value for key, value in payload.items() if key != "type"}
                prediction = ROISemanticPrediction.model_validate(payload)
                if set(prediction.concept_ids) - allowed_ids:
                    raise ValueError("ROI 模型返回了当前图谱之外的概念。")
                if bool(prediction.concept_ids) != (prediction.observation_state == "defect"):
                    raise ValueError("ROI 识别状态与缺陷概念列表不一致。")
                annotated.append(
                    region.model_copy(
                        update={
                            "semantic_candidates": prediction.concept_ids,
                            "semantic_source": f"vlm:{self.model}",
                            "semantic_status": (
                                "predicted"
                                if prediction.concept_ids
                                else "normal"
                                if prediction.observation_state == "normal"
                                else "unknown"
                            ),
                            "semantic_description": prediction.description,
                            "roi_path": str(roi_path),
                            "roi_bbox_xyxy": crop_bbox,
                        }
                    )
                )
        return annotated

    @staticmethod
    def _request(create, **kwargs):
        from openai import OpenAIError

        try:
            return create(**kwargs)
        except OpenAIError as exc:
            raise ROISemanticServiceError(
                "ROI 视觉服务调用失败，请检查服务配置或稍后重试。"
            ) from exc
