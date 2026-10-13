"use client";

import { useState, type FormEvent } from "react";
import { type Analysis, type ProcessPlan, formatNumber as num } from "@/lib/analysis";

function download(data: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([data], {type}));
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function NumericInput({name,label,value,min=0.001,max=10000,step="any",optional=false}: {name:string;label:string;value?:number;min?:number;max?:number;step?:string;optional?:boolean}) {
  return <label className="block text-xs text-slate-600">{label}<input className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900" type="number" name={name} defaultValue={value} required={!optional} min={min} max={max} step={step} placeholder={optional ? "未确认可留空" : "填写已确认值"} /></label>;
}

export default function ProcessPlanner({analysis}:{analysis:Analysis}) {
  const [plan,setPlan] = useState<ProcessPlan|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const features=analysis.impeller;
  if (!features || features.status !== "candidate") return <section className="mt-5 rounded-2xl border border-dashed border-slate-300 p-6"><h2 className="font-semibold">04 · 工艺参数草案</h2><p className="mt-2 text-sm leading-6 text-slate-500">当前模型未确认叶轮特征，保持通用分析模式。可检查轴向后重新分析；不会为普通零件套用叶轮工艺。</p></section>;

  async function generate(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); if(busy) return;
    const form=new FormData(event.currentTarget);
    const values:Record<string,string|number|boolean|null>={analysis_id:analysis.analysis_id ?? "", material:String(form.get("material")),confirmed_open_impeller:form.has("confirmed_open_impeller"),confirmed_cutting_inputs:form.has("confirmed_cutting_inputs")};
    for (const key of ["machine_axes","spindle_max_rpm","machine_diameter_limit_mm","machine_height_limit_mm","blank_diameter_mm","blank_height_mm","confirmed_channel_width_mm","confirmed_root_radius_mm","confirmed_min_wall_mm","cutting_speed_m_min","feed_per_tooth_mm","flutes","machine_rate_per_hour"]) {
      const text=form.get(key); values[key]=text === "" || text === null ? null : Number(text);
    }
    setBusy(true);setPlan(null);setError("");
    try {
      const response=await fetch("/api/process-plan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(values),signal:AbortSignal.timeout(15000)});
      const body=await response.json();
      if(!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "请检查输入参数的范围和完整性。");
      setPlan(body as ProcessPlan);
    } catch(e) {setError(e instanceof TypeError ? "分析服务无法连接，请重试。" : e instanceof Error ? e.message : "生成失败，请重试。");}
    finally{setBusy(false);}
  }

  function exportCsv() {
    if(!plan) return;
    const rows:(string|number)[][]=[["状态",plan.status,"非可执行 NC 程序"],["工序","名称","刀具","转速 rpm","进给 mm/min","ap mm","ae mm","审核状态"]];
    for(const s of plan.steps) rows.push([s.order,s.operation,s.tool_id ?? "待定",s.parameters?.rpm ?? "",s.parameters?.feed_mm_min ?? "",s.parameters?.ap_mm ?? "",s.parameters?.ae_mm ?? "",s.status]);
    rows.push(["阻断项",plan.blockers.join("；")],["说明",plan.disclaimer]);
    download("\uFEFF"+rows.map(row=>row.map(cell=>`"${String(cell).replaceAll('"','""')}"`).join(",")).join("\r\n"),"impeller-process-draft.csv","text/csv;charset=utf-8");
  }

  return <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-6" aria-label="工艺参数草案">
    <h2 className="text-lg font-semibold">04 · 工艺参数草案</h2>
    <p className="mt-3 text-sm leading-7 text-slate-500">补充工程约束后生成工序、刀具与参数。预填机床和切削值仅用于演示，请按实际设备及刀具资料修改；空隙弧长不会自动填入最小流道宽度。</p>
    <form onSubmit={generate} onChange={()=>{setPlan(null);setError("");}} className="mt-5">
      <fieldset disabled={busy} className="space-y-5 disabled:opacity-60">
        <legend className="sr-only">工艺输入</legend>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <label className="block text-xs text-slate-600">材料与状态<input name="material" required maxLength={80} placeholder="例如：6061-T6 铝合金" className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900" /></label>
          <label className="block text-xs text-slate-600">机床轴数<select name="machine_axes" defaultValue="5" className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"><option value="5">五轴（演示配置）</option><option value="3">三轴</option></select></label>
          <NumericInput name="spindle_max_rpm" label="机床最高转速 rpm" value={12000} max={100000}/>
          <NumericInput name="machine_rate_per_hour" label="机时单价 元/小时" value={300} min={0} max={100000}/>
          <NumericInput name="machine_diameter_limit_mm" label="机床工件直径限额 mm" value={200}/>
          <NumericInput name="machine_height_limit_mm" label="机床工件高度限额 mm" value={100}/>
          <NumericInput name="blank_diameter_mm" label="圆柱毛坯直径 mm" value={Math.ceil((features.outer_diameter_mm ?? 0)+10)}/>
          <NumericInput name="blank_height_mm" label="圆柱毛坯高度 mm" value={Math.ceil((features.axial_height_mm ?? 0)+6)}/>
          <NumericInput name="confirmed_channel_width_mm" label="人工确认最小流道宽度 mm"/>
          <NumericInput name="confirmed_root_radius_mm" label="人工确认最小根部圆角 R mm" optional max={1000}/>
          <NumericInput name="confirmed_min_wall_mm" label="人工确认最小壁厚 mm" optional max={1000}/>
          <NumericInput name="cutting_speed_m_min" label="切削速度 Vc m/min（演示初值）" value={120} max={1000}/>
          <NumericInput name="feed_per_tooth_mm" label="每齿进给 fz mm（演示初值）" value={0.03} max={0.5}/>
          <NumericInput name="flutes" label="刀具齿数（演示初值）" value={3} min={2} max={6} step="1"/>
        </div>
        <div className="space-y-3 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
          <label className="flex items-start gap-3"><input type="checkbox" name="confirmed_open_impeller" required className="mt-1"/><span>已人工确认该模型属于开式叶轮，并核对轴向与几何单位。</span></label>
          <label className="flex items-start gap-3"><input type="checkbox" name="confirmed_cutting_inputs" required className="mt-1"/><span>已核对材料、机床、尺寸与切削输入；了解演示刀具规格和未标定切深规则仍需验证。</span></label>
        </div>
        <button className="rounded-lg bg-blue-700 px-6 py-3 text-sm font-semibold text-white hover:bg-blue-800 disabled:bg-slate-400" disabled={busy}>{busy?"正在生成…":"生成工艺草案"}</button>
      </fieldset>
    </form>
    {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>}
    {plan && <div className="mt-7 border-t border-slate-200 pt-6">
      <div className="flex flex-wrap items-center justify-between gap-4"><p role="status" className={`font-semibold ${plan.status === "blocked" ? "text-red-700" : "text-amber-800"}`}>{plan.status === "blocked" ? "存在阻断项，方案不可采用" : "草案已生成，待工程审核"}</p><div className="flex flex-wrap gap-2"><button onClick={()=>download(JSON.stringify(plan,null,2),"impeller-process-draft.json","application/json")} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">导出参数包 JSON</button><button onClick={exportCsv} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">导出工序卡 CSV</button></div></div>
      <p className="mt-3 text-xs leading-6 text-slate-500">{plan.disclaimer}</p>
      {plan.blockers.length>0 && <ul className="mt-4 space-y-2 rounded-lg bg-red-50 p-4 text-sm text-red-800">{plan.blockers.map(x=><li key={x}>{x}</li>)}</ul>}
      {plan.warnings.length>0 && <ul className="mt-4 space-y-2 rounded-lg bg-amber-50 p-4 text-sm text-amber-900">{plan.warnings.map(x=><li key={x}>{x}</li>)}</ul>}
      <h3 className="mt-6 font-semibold">刀具与约束</h3><p className="mt-2 text-xs leading-6 text-slate-500">{plan.constraints.basis}；本次上限 Φ{num(plan.constraints.tool_diameter_cap_mm)} mm。</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">{plan.tools.map(tool=><div key={tool.id} className="rounded-xl bg-slate-50 p-4 text-sm"><p className="font-semibold">{tool.id} · Φ{tool.diameter_mm} {tool.kind}</p><p className="mt-2 text-xs text-slate-500">{tool.flutes} 齿 · 假设有效刃长 {tool.assumed_flute_length_mm} mm</p><p className="mt-2 text-xs leading-5 text-slate-500">{tool.source}</p></div>)}</div>
      <h3 className="mt-6 font-semibold">工序与切削参数</h3>
      <div className="mt-3 space-y-3">{plan.steps.map(s=><article key={s.order} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap justify-between gap-2"><h4 className="text-sm font-semibold">{s.order} · {s.operation} {s.tool_id && ` / ${s.tool_id}`}</h4><span className="text-xs text-slate-500">{s.status}</span></div><p className="mt-2 text-xs leading-6 text-slate-500">{s.strategy}</p>{s.parameters && <><p className="mt-3 text-sm leading-7">n = {num(s.parameters.rpm)} rpm · F = {num(s.parameters.feed_mm_min)} mm/min · ap = {num(s.parameters.ap_mm)} mm · ae = {num(s.parameters.ae_mm)} mm</p><p className="mt-1 text-xs leading-6 text-slate-500">实际 Vc {num(s.parameters.achieved_vc_m_min)} m/min{s.parameters.rpm_limited && " · 已按机床最高转速限幅"}。{s.parameters.note}</p><details className="mt-2 text-xs text-blue-700"><summary className="cursor-pointer">计算依据</summary><p className="mt-2 leading-6">{s.parameters.basis}</p></details></>}</article>)}</div>
      <h3 className="mt-6 font-semibold">理想连续粗加工估算 · 非总工时</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">{[["毛坯总去除体积",plan.estimate.removed_volume_mm3,"mm³"],["理想粗加工时间",plan.estimate.ideal_roughing_minutes,"min"],["对应机时费用",plan.estimate.ideal_roughing_cost,"元"]].map(([label,value,unit])=><div key={String(label)} className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-lg font-semibold">{num(value as number|null)} <span className="text-xs font-normal">{unit}</span></p></div>)}</div>
      <p className="mt-3 text-xs leading-6 text-slate-500">{plan.estimate.basis}</p>
      <details className="mt-5 text-sm"><summary className="cursor-pointer font-medium">工程审核待办</summary><ul className="mt-3 space-y-2 text-xs leading-6 text-slate-600">{plan.required_review.map(x=><li key={x}>{x}</li>)}</ul></details>
    </div>}
  </section>;
}
