"use client";

import dynamic from "next/dynamic";
import ImpellerPanel from "@/components/impeller-panel";
import ProcessPlanner from "@/components/process-planner";
import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { type Analysis, formatNumber as num } from "@/lib/analysis";

const ModelViewer = dynamic(() => import("@/components/model-viewer"), {
  ssr: false,
  loading: () => <div className="grid h-[480px] place-items-center rounded-2xl bg-slate-900 text-slate-300">正在加载三维视图…</div>,
});
const labels: Record<string, string> = {
  triangles: "三角面", mesh_vertices: "网格顶点", faces: "曲面", edges: "边", vertices: "顶点", solids: "实体",
  Plane: "平面", Cylinder: "圆柱面", Cone: "圆锥面", Sphere: "球面", Torus: "环面", BSplineSurface: "B 样条曲面", BezierSurface: "贝塞尔曲面",
  SurfaceOfRevolution: "旋转曲面", SurfaceOfExtrusion: "拉伸曲面", OffsetSurface: "偏置曲面", OtherSurface: "其他曲面",
  watertight: "网格封闭", winding_consistent: "法向一致", components: "连通分量", volume_available: "体积计算条件", brep_valid: "B-rep 有效性",
};

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [unit, setUnit] = useState("mm");
  const [axis, setAxis] = useState("Z");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Analysis | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const isStep = /\.(step|stp)$/i.test(file?.name ?? "");

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setError("");
    setResult(null);
    if (!/\.(stl|step|stp)$/i.test(file.name)) { setError("请选择 STL、STEP 或 STP 文件。"); return; }
    if (file.size > 20 * 1024 * 1024) { setError("文件不能超过 20 MiB，请简化模型后重试。"); return; }
    if (file.size === 0) { setError("文件为空，请重新选择。"); return; }
    setBusy(true);
    try {
      const query = new URLSearchParams({ filename: file.name, unit, axis });
      const response = await fetch(`/api/analyze?${query}`, {
        method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
        signal: AbortSignal.timeout(90_000),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "分析服务暂不可用，请确认后端已启动后重试。");
      if (!data || !Array.isArray(data.dimensions_mm)) throw new Error("分析结果格式异常，请重试。");
      setResult(data as Analysis);
    } catch (failure) {
      setError(failure instanceof Error && failure.name === "TimeoutError" ? "请求超时，请检查连接或简化模型后重试。" : failure instanceof TypeError ? "无法连接分析服务，请确认前后端服务已启动。" : failure instanceof Error ? failure.message : "分析失败，请重试。");
    } finally { setBusy(false); }
  }

  function downloadReport() {
    if (!result) return;
    const { preview, ...report } = result;
    const blob = new Blob([JSON.stringify({ ...report, preview_triangle_count: preview?.triangle_count ?? null }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${result.filename.replace(/\.[^.]+$/, "")}-geometry.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="text-xs font-bold tracking-[.2em] text-blue-700">IMPELLER PROCESS · 0.3</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">从三维几何开始，理解加工对象</h1>
        <p className="mt-4 max-w-3xl leading-7 text-slate-500">导入真实模型，测量尺寸、面积与体积，为叶轮工艺规划建立可追溯的几何基础。</p>
      </div>
      <span className="rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-medium text-blue-700">01 → 04 · 几何与工艺草案</span>
    </header>

    <form onSubmit={analyze} className="mt-9 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-end gap-5">
        <div className="min-w-0 flex-1 basis-72">
          <label htmlFor="model-file" className="block text-sm font-semibold">三维模型文件</label>
          <input ref={input} id="model-file" type="file" accept=".stl,.step,.stp" disabled={busy}
            onChange={(event) => { setFile(event.target.files?.[0] ?? null); setResult(null); setError(""); }}
            className="mt-3 block w-full text-sm text-slate-500 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-100 file:px-4 file:py-3 file:font-medium file:text-slate-700 hover:file:bg-slate-200" />
        </div>
        <div>
          <label htmlFor="model-unit" className="block text-sm font-semibold">{isStep ? "STEP 单位" : "STL 原始单位"}</label>
          <select id="model-unit" value={unit} disabled={busy || isStep} onChange={(event) => { setUnit(event.target.value); setResult(null); }} className="mt-3 rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm disabled:bg-slate-100">
            {isStep ? <option value={unit}>从文件自动读取</option> : <><option value="mm">毫米 mm</option><option value="cm">厘米 cm</option><option value="m">米 m</option><option value="inch">英寸 inch</option></>}
          </select>
        </div>
        <label className="text-sm font-semibold">叶轮轴向
          <select aria-label="叶轮轴向" value={axis} disabled={busy} onChange={event => {setAxis(event.target.value);setResult(null);}} className="mt-3 block rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm">
            {["X","Y","Z"].map(value => <option key={value} value={value}>{value} 轴</option>)}
          </select>
        </label>
        <button type="submit" disabled={!file || busy} className="rounded-lg bg-blue-700 px-7 py-3 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-300">{busy ? "正在解析…" : "开始几何分析"}</button>
      </div>
      <p className="mt-4 text-xs leading-6 text-slate-500">支持 STEP / STP / STL · 最大 20 MiB · 所有结果统一为 mm · 上传文件不持久保存；几何摘要在内存保留最多 30 分钟供工艺生成</p>
      {busy && <p role="status" className="mt-4 text-sm text-blue-700">正在读取几何并生成预览，请稍候。复杂模型解析最多等待 45 秒。</p>}
      {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>}
    </form>

    {result ? <section className="mt-7" aria-label="几何分析结果">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0"><h2 className="break-all text-xl font-semibold">{result.filename}</h2><p className="mt-1 text-xs text-slate-500">{result.method} · {result.unit_source}</p></div>
        <button onClick={downloadReport} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm hover:bg-slate-50">导出几何报告 JSON</button>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div>
          {result.preview ? <ModelViewer analysis={result} /> : <div className="grid h-72 place-items-center rounded-2xl bg-slate-900 p-8 text-sm text-slate-300">当前模型未生成交互预览，几何测量结果可在右侧查看。</div>}
          <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-5">
            <h3 className="text-sm font-semibold text-amber-900">测量说明与质量提示</h3>
            <ul className="mt-3 space-y-2 text-xs leading-6 text-amber-900">{result.warnings.map((warning) => <li key={warning}>• {warning}</li>)}</ul>
          </div>
        </div>
        <div className="min-w-0 space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <h3 className="text-sm font-semibold text-slate-500">包围盒尺寸 · 原始坐标轴</h3>
            <div className="mt-4 grid grid-cols-3 gap-3">{result.dimensions_mm.map((value, i) => <div key={i}><p className="text-xs text-slate-400">{"XYZ"[i]} / mm</p><p className="mt-1 break-all text-xl font-semibold">{num(value)}</p></div>)}</div>
            <div className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-100 pt-5">
              <div><p className="text-xs text-slate-500">表面积 / mm²</p><p className="mt-2 break-all text-xl font-semibold">{num(result.surface_area_mm2)}</p></div>
              <div><p className="text-xs text-slate-500">体积 / mm³</p><p className="mt-2 break-all text-xl font-semibold">{num(result.volume_mm3)}</p></div>
            </div>
            <p className="mt-5 text-xs leading-6 text-slate-500">实体重心 X / Y / Z（mm）：<br /><span className="text-slate-800">{result.center_of_mass_mm?.map(num).join(" / ") ?? "不可用，参见质量提示"}</span></p>
          </section>
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <h3 className="text-sm font-semibold">{result.format === "STL" ? "网格统计" : "CAD 拓扑与曲面"}</h3>
            <dl className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3 text-sm">{Object.entries({ ...result.topology, ...result.surface_types }).map(([key, value]) => <div key={key} className="flex justify-between gap-2"><dt className="text-slate-500">{labels[key] ?? key}</dt><dd className="font-medium">{num(value)}</dd></div>)}</dl>
            {result.format === "STL" && <p className="mt-4 text-xs leading-5 text-slate-400">STL 不含 CAD 曲面类型与拓扑面信息，网格三角面不等于曲面数量。</p>}
          </section>
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <h3 className="text-sm font-semibold">几何检查</h3>
            <dl className="mt-4 space-y-3 text-sm">{Object.entries(result.checks).map(([key, value]) => <div key={key} className="flex justify-between gap-4"><dt className="text-slate-500">{labels[key] ?? key}</dt><dd className={value === false ? "text-amber-700" : "text-slate-800"}>{typeof value === "boolean" ? value ? "通过" : "未通过" : value}</dd></div>)}</dl>
          </section>
        </div>
      </div>
      <p role="status" className="mt-6 rounded-xl bg-blue-50 px-5 py-4 text-sm text-blue-900">解析完成 · {result.classification}</p>
      {result.impeller && <ImpellerPanel features={result.impeller} />}
      <ProcessPlanner key={result.analysis_id} analysis={result} />
    </section> : !busy && <section className="mt-7 grid gap-5 sm:grid-cols-3" aria-label="能力说明">
      {[["01", "真实几何测量", "STEP 读取原始 CAD 几何；STL 计算三角网格尺寸、面积和适用的体积。"], ["02", "可检查的结果", "展示数据来源、单位与几何检查结果；不满足条件的体积和重心明确标记不可用。"], ["03", "叶轮候选与工艺草案", "通过周期截面识别候选叶片数，人工核对后生成带约束与计算依据的工艺参数草案。"]].map(([step, title, description]) => <div key={step} className="rounded-2xl border border-slate-200 bg-white p-6"><p className="text-xs font-semibold text-blue-600">{step}</p><h2 className="mt-4 font-semibold">{title}</h2><p className="mt-3 text-sm leading-7 text-slate-500">{description}</p></div>)}
    </section>}
  </main>;
}
