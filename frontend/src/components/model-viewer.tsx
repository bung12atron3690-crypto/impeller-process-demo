"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { Analysis } from "@/lib/analysis";

export default function ModelViewer({ analysis }: { analysis: Analysis }) {
  const container = useRef<HTMLDivElement>(null);
  const reset = useRef<() => void>(() => {});

  useEffect(() => {
    const host = container.current;
    const preview = analysis.preview;
    if (!host || !preview) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      host.textContent = "当前浏览器无法启用 WebGL，几何分析结果仍可查看与导出。";
      return () => { host.textContent = ""; };
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x101e32);
    renderer.domElement.setAttribute("aria-label", `${analysis.filename} 三维预览，可用鼠标旋转和缩放`);
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 100);
    camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.minDistance = 0.25;
    controls.maxDistance = 15;
    const geometry = new THREE.BufferGeometry();
    const center = analysis.bounds_mm[0].map((min, i) => (min + analysis.bounds_mm[1][i]) / 2);
    const scale = Math.max(...analysis.dimensions_mm, 0.000001);
    const points = preview.positions.map((value, i) => (value - center[i % 3]) / scale * 2);
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    geometry.setIndex(preview.indices);
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({ color: 0x79b8d8, metalness: 0.35, roughness: 0.45, flatShading: analysis.format === "STL", side: THREE.DoubleSide });
    scene.add(new THREE.Mesh(geometry, material));
    scene.add(new THREE.HemisphereLight(0xe7f4ff, 0x4a5572, 3));
    const light = new THREE.DirectionalLight(0xffffff, 3);
    light.position.set(3, -4, 5);
    scene.add(light);
    const axes = new THREE.AxesHelper(1.4);
    scene.add(axes);
    const fit = () => {
      camera.position.set(3.5, -4.5, 3);
      controls.target.set(0, 0, 0);
      controls.update();
    };
    reset.current = fit;
    fit();
    const resize = () => {
      const width = host.clientWidth;
      const height = host.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();
    renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
    return () => {
      observer.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      geometry.dispose();
      material.dispose();
      axes.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      reset.current = () => {};
    };
  }, [analysis]);

  return <div className="min-w-0 overflow-hidden rounded-2xl bg-[#101e32] text-slate-200">
    <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
      <span className="text-sm">三维模型 · {analysis.format}</span>
      <button className="rounded border border-slate-500 px-3 py-1 text-xs hover:bg-white/10" onClick={() => reset.current()}>重置视角</button>
    </div>
    <div ref={container} className="h-[360px] w-full sm:h-[480px]" />
    <p className="px-5 pb-2 text-xs text-slate-400">拖动旋转 · 滚轮缩放 · 右键平移 · 坐标轴：X 红 / Y 绿 / Z 蓝</p>
    <p className="px-5 pb-5 text-xs leading-5 text-slate-400">{analysis.preview?.note}</p>
  </div>;
}
