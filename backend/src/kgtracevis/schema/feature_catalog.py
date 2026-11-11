"""Shared producer vocabulary and authoring metadata, never case-specific values.

Finite values describe the registered deterministic producer contract. External
labels may still arrive in Evidence; explicit sourced ValueBindings can translate
equivalent terms. Appearance estimates remain open, not an anatomical ontology.
"""

from kgtracevis.schema.unified_knowledge import FeatureDefinition

MORPHOLOGY_LINEAR = "linear"
MORPHOLOGY_SPOT = "spot"
MORPHOLOGY_SCATTERED = "scattered"
MORPHOLOGY_DENSE = "dense"
MASK_MORPHOLOGIES = (MORPHOLOGY_LINEAR, MORPHOLOGY_SPOT, MORPHOLOGY_SCATTERED, MORPHOLOGY_DENSE)
LOCATION_EDGE = "edge"
LOCATION_SURFACE = "surface"
MASK_LOCATIONS = (LOCATION_EDGE, LOCATION_SURFACE)
WAFER_PATTERNS = (
    "center",
    "donut",
    "edge_loc",
    "edge_ring",
    "loc",
    "random",
    "scratch",
    "nearfull",
)


def _feature(
    identity, kind, definition, unit=None, *, reference=False, values=None, role="diagnostic"
):
    return FeatureDefinition(
        feature_id=identity,
        value_kind=kind,
        definition=definition,
        unit=unit,
        requires_reference=reference,
        allowed_values=list(values) if values is not None else None,
        semantic_role=role,
    )


_FEATURES = [
    _feature(
        "detection.anomaly_present",
        "boolean",
        "当前范围的显式异常布尔量，不含原因信息。图像为检测器实际输出；"
        "过程为匹配正常参考的PCA残差能量门控；晶圆为非空有效网格中存在失效die。",
        role="presence_gate",
    ),
    _feature(
        "geometry.area_ratio",
        "number",
        "区域连通分量像素数／检测网格总像素数。",
        "1",
    ),
    _feature("geometry.aspect_ratio", "number", "轴对齐包围框长边／短边。", "1"),
    _feature(
        "geometry.eccentricity",
        "number",
        "由连通分量坐标协方差特征值计算的离心率，范围[0,1]。",
        "1",
    ),
    _feature("geometry.component_count", "number", "本区域保留的连通分量数。", "1"),
    _feature(
        "geometry.morphology",
        "category",
        "掩膜粗形态，不是缺陷类别。原始单ROI：长宽比>=3或离心率>=.95为linear，"
        "否则spot。外部聚合几何依次检查：离心率>=.8或长宽比>=3为linear；"
        "分量>=4为scattered；面积占比>=.35为dense；其余正面积为spot。"
        "外部术语需明确等价绑定，不自动猜测。",
        values=MASK_MORPHOLOGIES,
    ),
    _feature(
        "geometry.location",
        "category",
        "图像网格质心：任一归一化坐标<=.2或>=.8为edge，否则surface。"
        "不是瓶口等解剖部位；外部术语需明确等价绑定。",
        values=MASK_LOCATIONS,
    ),
    _feature(
        "appearance.semantic_candidates",
        "candidate_set",
        "ROI视觉语言模型的开放外观候选，不设有限枚举。规则以candidate_contains匹配；"
        "缺少某词仍为未知。粗粒度玻璃破损描述不能补出具体瓶口或缺损部位。",
    ),
    _feature(
        "appearance.defect_present",
        "boolean",
        "视觉语言模型显式判断正常／缺陷；不确定时缺失。",
        role="presence_gate",
    ),
    _feature(
        "statistics.mean_z",
        "number",
        "窗口内(x-正常均值)/正常尺度的均值，保留正负方向。",
        "1",
        reference=True,
    ),
    _feature(
        "statistics.std_z",
        "number",
        "窗口标准化样本的总体标准差（ddof=0）。",
        "1",
        reference=True,
    ),
    _feature(
        "statistics.slope_z",
        "number",
        "标准化样本对样本序号的最小二乘斜率，保留正负方向。",
        "1/sample",
        reference=True,
    ),
    _feature(
        "residual.contribution",
        "number",
        "归一化PCA残差平方贡献占比；保留完整向量，不是原因概率。",
        "1",
        reference=True,
    ),
    _feature(
        "residual.energy",
        "number",
        "本窗口PCA重建残差平方的平均能量。",
        "1",
        reference=True,
    ),
    _feature(
        "residual.normal_limit",
        "number",
        "匹配正常参考数据的残差能量99分位门限。",
        "1",
        reference=True,
        role="context",
    ),
    _feature(
        "series.raw_values",
        "array_ref",
        "通道原始物理量采样数组；用于定位与曲线，不是最终排名特征。",
        role="context",
    ),
    _feature(
        "spatial.failure_density",
        "number",
        "指定区域失效die数／有效die数；区域为空时缺失。",
        "1",
    ),
    _feature("spatial.valid_die_count", "number", "编码为1或2的有效die数。", "1", role="context"),
    _feature("spatial.failed_die_count", "number", "编码为2的失效die数。", "1"),
    _feature("spatial.component_count", "number", "失效die的八邻域连通分量数。", "1"),
    _feature(
        "spatial.largest_component_ratio",
        "number",
        "最大八邻域连通分量大小／失效die数；无失效时缺失。",
        "1",
    ),
    _feature(
        "spatial.linearity",
        "number",
        "1-坐标协方差最小／最大特征值；失效die少于3时缺失。",
        "1",
    ),
    _feature(
        "spatial.edge_sector_participation",
        "number",
        "边缘有效die的扇区参与度：以12个30°扇区、每扇区至少5个有效die、"
        "至少8个可用扇区且总失效密度非零为前提；各扇区失效密度归一为p，"
        "计算1/(k·Σp²)。越高表示失效分布于越多扇区，不是失效比例或概率。",
        "1",
    ),
    _feature(
        "classifier.pattern",
        "category",
        "独立ResNet模型的八类图案输出，不读取数据集原生标签。",
        values=WAFER_PATTERNS,
    ),
    _feature("spatial.grid", "array_ref", "真实晶圆网格：0背景、1正常、2失效。", role="context"),
]
FEATURE_CATALOG = {feature.feature_id: feature for feature in _FEATURES}
VISUAL_FEATURE_IDS = (
    "detection.anomaly_present",
    "geometry.area_ratio",
    "geometry.aspect_ratio",
    "geometry.eccentricity",
    "geometry.component_count",
    "geometry.morphology",
    "geometry.location",
    "appearance.semantic_candidates",
    "appearance.defect_present",
)
PROCESS_FEATURE_IDS = (
    "detection.anomaly_present",
    "statistics.mean_z",
    "statistics.std_z",
    "statistics.slope_z",
    "residual.contribution",
    "residual.energy",
    "residual.normal_limit",
    "series.raw_values",
)
SPATIAL_FEATURE_IDS = (
    "detection.anomaly_present",
    "spatial.failure_density",
    "spatial.valid_die_count",
    "spatial.failed_die_count",
    "spatial.component_count",
    "spatial.largest_component_ratio",
    "spatial.linearity",
    "spatial.edge_sector_participation",
    "classifier.pattern",
    "spatial.grid",
)


def feature_definitions(identities: tuple[str, ...]) -> list[FeatureDefinition]:
    """Return independent definitions so callers cannot mutate the shared catalog."""
    return [FEATURE_CATALOG[identity].model_copy(deep=True) for identity in identities]


def authoring_feature_role(feature: FeatureDefinition) -> str:
    """Known producer semantics cannot be bypassed by older captured metadata."""
    registered = FEATURE_CATALOG.get(feature.feature_id)
    return (
        registered.semantic_role if registered is not None else feature.semantic_role
    ) or "diagnostic"
