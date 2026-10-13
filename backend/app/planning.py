"""Reviewable process drafts. No CAM paths, postprocessing, or NC execution."""
from math import floor, pi
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .schemas import Analysis

RULE_VERSION = "process-draft-v1"
TOOL_DIAMETERS = (2, 3, 4, 6, 8, 10, 12, 16)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    analysis_id: str = Field(min_length=1, max_length=100)
    confirmed_open_impeller: StrictBool
    confirmed_cutting_inputs: StrictBool
    material: str = Field(min_length=1, max_length=80)
    machine_axes: Literal[3, 5] = 5
    spindle_max_rpm: float = Field(gt=0, le=100_000)
    machine_diameter_limit_mm: float = Field(gt=0, le=10_000)
    machine_height_limit_mm: float = Field(gt=0, le=10_000)
    blank_diameter_mm: float = Field(gt=0, le=10_000)
    blank_height_mm: float = Field(gt=0, le=10_000)
    confirmed_channel_width_mm: float = Field(gt=0, le=10_000)
    confirmed_root_radius_mm: float | None = Field(default=None, gt=0, le=1000)
    confirmed_min_wall_mm: float | None = Field(default=None, gt=0, le=1000)
    cutting_speed_m_min: float = Field(gt=0, le=1000)
    feed_per_tooth_mm: float = Field(ge=0.001, le=0.5)
    flutes: int = Field(ge=2, le=6)
    machine_rate_per_hour: float = Field(ge=0, le=100_000)


def generate_plan(analysis: Analysis, inputs: PlanRequest) -> dict:
    features = analysis.impeller or {}
    if features.get("status") != "candidate" or not inputs.confirmed_open_impeller:
        raise ValueError("仅对人工确认的叶轮候选生成专项工艺草案。")
    if not inputs.confirmed_cutting_inputs:
        raise ValueError("请确认已核对材料及切削参数输入。")
    if analysis.volume_mm3 is None:
        raise ValueError("缺少可靠的单实体体积，无法生成当前工艺草案。")
    diameter, height = features["outer_diameter_mm"], features["axial_height_mm"]
    if inputs.blank_diameter_mm + 1e-6 < diameter or inputs.blank_height_mm + 1e-6 < height:
        raise ValueError("毛坯尺寸小于模型包络，请检查毛坯或单位。")
    if inputs.confirmed_channel_width_mm >= diameter:
        raise ValueError("确认的流道宽度不能大于等于零件外径。")
    if inputs.confirmed_root_radius_mm is not None and inputs.confirmed_root_radius_mm * 2 >= diameter:
        raise ValueError("根部圆角尺寸与零件外径不相容。")
    blockers, warnings = [], []
    if inputs.machine_axes != 5:
        blockers.append("当前叶轮模板要求五轴机床；三轴可达性未验证。")
    if inputs.blank_diameter_mm > inputs.machine_diameter_limit_mm or inputs.blank_height_mm > inputs.machine_height_limit_mm:
        blockers.append("毛坯超出输入的机床工件尺寸限额。")
    thin_wall = inputs.confirmed_min_wall_mm is not None and inputs.confirmed_min_wall_mm < 3
    if thin_wall:
        warnings.append("确认壁厚小于 3 mm，按演示规则降低切深/切宽；仍需验证变形和振动。")
    if inputs.confirmed_min_wall_mm is None:
        warnings.append("最小壁厚未确认，未进行薄壁风险约束。")
    # The diameter cap is based on operator-confirmed clearance, not sampled arcs.
    diameter_cap = 0.6 * inputs.confirmed_channel_width_mm
    rough_candidates = [d for d in TOOL_DIAMETERS if d <= diameter_cap]
    if not rough_candidates:
        blockers.append("演示刀具库中没有满足流道直径上限的粗加工刀具。")
    rough_diameter = max(rough_candidates) if rough_candidates else None
    tools = []

    def tool(tool_id, kind, diameter, depth_ratio):
        reach = diameter * depth_ratio
        if reach < height:
            blockers.append(f"{tool_id} 演示刀具有效刃长 {reach:g} mm 小于轴向包络 {height:g} mm，需确认长刃刀或调整工艺。")
        return {"id": tool_id, "kind": kind, "diameter_mm": diameter, "flutes": inputs.flutes,
                "assumed_flute_length_mm": reach, "source": "内置演示刀具规格；需替换为实际刀具和刀柄数据"}

    if rough_diameter:
        tools.append(tool("T01", "平底立铣刀", rough_diameter, 3))
    # Root-radius-dependent finishing selection remains unavailable until confirmed.
    finish_diameter = None
    if inputs.confirmed_root_radius_mm is not None:
        choices = [d for d in TOOL_DIAMETERS if d <= min(diameter_cap, 2 * inputs.confirmed_root_radius_mm)]
        if choices:
            finish_diameter = max(choices)
            tools.append(tool("T02", "球头铣刀", finish_diameter, 4))
        else:
            blockers.append("演示刀具库中没有同时满足流道与根部圆角约束的球头刀。")
    else:
        warnings.append("根部圆角未确认，叶片精加工与清根刀具/参数保持待定。")

    def parameters(diameter, finishing=False):
        requested = 1000 * inputs.cutting_speed_m_min / (pi * diameter)
        rpm = floor(min(requested, inputs.spindle_max_rpm))
        if rpm < 1:
            raise ValueError("切削速度与转速上限组合无法得到有效整数转速。")
        feed = rpm * inputs.flutes * inputs.feed_per_tooth_mm
        factor = 0.5 if thin_wall else 1.0
        return {"rpm": rpm, "feed_mm_min": round(feed, 3), "requested_vc_m_min": inputs.cutting_speed_m_min,
                "achieved_vc_m_min": round(pi * diameter * rpm / 1000, 3),
                "fz_mm_tooth": inputs.feed_per_tooth_mm,
                "ap_mm": round(diameter * (0.05 if finishing else 0.25) * factor, 3),
                "ae_mm": round(diameter * (0.05 if finishing else 0.20) * factor, 3),
                "rpm_limited": requested > inputs.spindle_max_rpm,
                "basis": "n=min(1000×Vc/(π×D),机床上限)，向下取整；F=n×z×fz；ap/ae 为未标定演示比例",
                "note": "球头刀 Vc 按名义直径计算，实际接触直径与刀轴姿态仍需 CAM 校核" if finishing else "未考虑刀具磨损、振动或局部包角变化"}

    rough_parameters = parameters(rough_diameter) if rough_diameter else None
    finish_parameters = parameters(finish_diameter, True) if finish_diameter else None
    steps = [
        {"order": 10, "operation": "毛坯与基准准备", "strategy": "确认材料状态、装夹基准和余量；按图纸确定车削/铣削基准", "tool_id": None, "parameters": None, "status": "待图纸与夹具确认"},
        {"order": 20, "operation": "流道粗加工", "strategy": "五轴分层粗加工，保留叶片及根部精加工余量；余量需按刚度与图纸确定", "tool_id": "T01" if rough_diameter else None, "parameters": rough_parameters, "status": "草案，待验证"},
        {"order": 30, "operation": "叶片与流道精加工", "strategy": "球头刀五轴点铣；刀轴姿态、残留高度与进退刀路径由 CAM 确定", "tool_id": "T02" if finish_diameter else None, "parameters": finish_parameters, "status": "草案，待验证" if finish_diameter else "待根部圆角与刀具确认"},
        {"order": 40, "operation": "根部清根", "strategy": "根据残料仿真与根部圆角选择清根路径", "tool_id": "T02" if finish_diameter else None, "parameters": finish_parameters, "status": "待残料与碰撞仿真"},
        {"order": 50, "operation": "去毛刺与检验", "strategy": "按图纸检验叶片轮廓、根部圆角、关键尺寸和表面质量；平衡要求另行确认", "tool_id": None, "parameters": None, "status": "待质量要求"},
    ]
    blank_volume = pi * inputs.blank_diameter_mm**2 / 4 * inputs.blank_height_mm
    removed_volume = max(0.0, blank_volume - analysis.volume_mm3)
    ideal_minutes = None
    if rough_parameters and not blockers:
        removal_rate = rough_parameters["feed_mm_min"] * rough_parameters["ap_mm"] * rough_parameters["ae_mm"]
        if removal_rate > 0:
            ideal_minutes = removed_volume / removal_rate
    return {"schema_version": "0.3", "rule_version": RULE_VERSION, "status": "blocked" if blockers else "review_required",
            "title": "开式叶轮工艺参数草案", "executable_nc": False,
            "source": {"analysis_id": analysis.analysis_id, "filename": analysis.filename, "sha256": analysis.source_sha256,
                       "geometry_method": analysis.method, "recognition": features},
            "inputs": inputs.model_dump(), "tools": tools, "steps": steps,
            "constraints": {"tool_diameter_cap_mm": diameter_cap, "basis": "刀具直径 ≤ 0.6 × 人工确认最小流道宽度（演示余隙规则）"},
            "estimate": {"currency": "CNY", "blank_volume_mm3": blank_volume, "removed_volume_mm3": removed_volume,
                         "ideal_roughing_minutes": ideal_minutes,
                         "ideal_roughing_cost": ideal_minutes / 60 * inputs.machine_rate_per_hour if ideal_minutes is not None else None,
                         "total_minutes": None, "total_cost": None,
                         "basis": "仅用圆柱毛坯体积减零件体积，再除以 F×ap×ae；假设全部去除量按同一粗加工参数连续切削，不是加工节拍或报价。未包含装夹、空行程、精加工、换刀和检验。"},
            "blockers": blockers, "warnings": warnings,
            "required_review": ["材料状态及刀具厂家推荐的 Vc/fz", "实际机床行程、回转范围、功率与夹具", "实际刀具刃长、悬伸、刀柄和全路径碰撞", "图纸公差、粗糙度、余量与变形", "CAM 刀路、后处理、仿真与试切"],
            "disclaimer": "这是规则驱动的可审阅草案，不是可直接上机的 NC 程序。材料和切削参数来自用户输入，系统尚未验证其适配性。"}
