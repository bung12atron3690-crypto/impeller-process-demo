import type { ImpellerFeatures } from "@/lib/analysis";
import { formatNumber as num } from "@/lib/analysis";

export default function ImpellerPanel({ features }: { features: ImpellerFeatures }) {
  const candidate = features.status === "candidate";
  return <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-6" aria-label="叶轮专项识别">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">01 · 叶轮专项识别</h2><span className={`rounded-full px-3 py-1 text-xs ${candidate ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-600"}`}>{candidate ? "叶轮候选 · 待人工确认" : "未确认叶轮特征"}</span></div>
    <p className="mt-3 text-xs text-slate-500">分析轴向 {features.axis} · 周期截面识别 · {features.method}</p>
    <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-600">{features.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
    {candidate && <div className="mt-6 grid grid-cols-2 gap-5 sm:grid-cols-4">
      {[["候选叶片数", features.blade_count, "片"], ["径向包络直径", features.outer_diameter_mm, "mm"], ["轴向总高", features.axial_height_mm, "mm"], ["采样证据一致率", features.evidence_ratio * 100, "%"]].map(([label, value, unit]) => <div key={String(label)} className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-xl font-semibold">{num(value as number | null)} <span className="text-xs font-normal">{unit}</span></p></div>)}
    </div>}
    {features.rings.length > 0 && <details className="mt-5 text-sm">
      <summary className="cursor-pointer font-medium text-blue-700">查看 9 个圆环的采样证据</summary>
      <p className="mt-3 text-xs leading-6 text-slate-500">每圈 720 个采样点。材料/空隙弧长仅描述所采样圆环，不等于真实壁厚或最小流道宽度。</p>
      <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[540px] text-left text-xs"><thead><tr className="border-b text-slate-500">{["相对高度", "半径 mm", "区间数", "节距变异", "最小材料弧长 mm", "最小空隙弧长 mm"].map(x => <th key={x} className="p-2 font-medium">{x}</th>)}</tr></thead><tbody>{features.rings.map((ring,i) => <tr key={i} className="border-b border-slate-100"><td className="p-2">{num(ring.height_fraction*100)}%</td><td>{num(ring.radius_mm)}</td><td>{ring.count}</td><td>{num(ring.pitch_cv*100)}%</td><td>{num(ring.material_arc_mm)}</td><td>{num(ring.gap_arc_mm)}</td></tr>)}</tbody></table></div>
    </details>}
    <details className="mt-4 text-sm"><summary className="cursor-pointer text-slate-500">识别范围与尚未提取的特征</summary><ul className="mt-3 space-y-2 text-xs leading-6 text-slate-500">{features.limitations.map(x => <li key={x}>{x}</li>)}</ul></details>
  </section>;
}
