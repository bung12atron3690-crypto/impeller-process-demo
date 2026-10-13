"""Isolate native CAD parsing from the API process; parent enforces wall timeout."""
import json
import sys
from pathlib import Path

from .features import recognize
from .geometry import GeometryError, analyze_step, analyze_stl


def main() -> None:
    path, output, unit = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    try:
        result = analyze_stl(path, unit) if path.suffix == ".stl" else analyze_step(path)
        try:
            result.impeller = recognize(result, sys.argv[4] if len(sys.argv) > 4 else "Z")
            result.classification = "疑似开式叶轮：需人工确认" if result.impeller["status"] == "candidate" else "未确认叶轮特征，保留通用几何模式"
        except Exception:
            result.warnings.append("专项识别未完成，已保留通用几何分析。")
        output.write_text(json.dumps({"result": result.model_dump()}, allow_nan=False), encoding="utf-8")
    except GeometryError as exc:
        output.write_text(json.dumps({"error": str(exc)}), encoding="utf-8")
    except Exception:
        output.write_text(json.dumps({"error": "无法解析该模型，请检查几何完整性或重新导出文件。"}), encoding="utf-8")


if __name__ == "__main__":
    main()
