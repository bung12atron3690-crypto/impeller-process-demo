# impeller-process-demo

开式叶轮智能工艺参数推荐 Demo，重点面向赛题 **1：叶轮模型智能解析** 和 **4：工艺路线与参数包生成**。

当前版本 0.3 已打通 **STL/STEP 上传 → 真实几何测量 → 叶轮候选识别 → 人工输入工程约束 → 工艺参数草案与导出**。

专项识别采用周期截面启发式，已用生成模型验证候选叶片数；尚未用真实赛题叶轮验证。根部圆角、真实最小流道宽度、壁厚和曲率尚未自动提取。输出为待审核工艺草案，不是可执行 NC 程序。

## 当前能力

| 内容 | STL | STEP / STP |
| --- | --- | --- |
| 几何引擎 | trimesh 三角网格 | OpenCascade B-rep |
| 单位 | 用户选择 mm / cm / m / inch | 按文件声明转换为 mm |
| 尺寸、面积 | 网格近似 | CAD 几何测量与积分 |
| 体积、实体重心 | 单一封闭、法向一致、正向网格 | 单一有效实体 |
| 统计 | 三角面、网格顶点、连通分量 | 面、边、顶点、实体、曲面类型 |
| 三维预览 | 原始三角网格 | CAD 曲面离散 |
| JSON 报告 | 支持 | 支持 |

所有尺寸统一为 mm，面积为 mm²，体积为 mm³。包围盒沿原始坐标轴，重心保留模型原始坐标系；预览仅为方便观察而居中、缩放。没有把包围盒尺寸当作叶轮直径。

候选识别在两个格式的离散网格上使用同一算法。用户选择 X/Y/Z 轴，系统检查单侧底盘、开放端和多截面周期薄片；证据不足时保留通用模式。详细阈值见 [识别与工艺规则](docs/recognition-and-planning.md)。

## 环境与目录

推荐 Node.js 24 LTS + Python 3.12；已在 Linux x86_64 云环境验证。OpenCascade 通过 `cadquery-ocp` wheel 安装，首次安装会下载较大的原生依赖。无需数据库、API 密钥或单独安装桌面 CAD 软件。

```text
frontend/         Next.js + TypeScript + Tailwind + Three.js
backend/app/      FastAPI、几何解析、隔离解析进程
backend/tests/    几何与上传 API 测试
models/samples/   可直接上传的几何基准模型
data/            后续工艺规则数据
docs/            开发计划与技术边界
```

前端默认使用 Webpack，以兼容当前云环境对 Turbopack 临时端口的限制。

## 阿里云公网部署

已提供 Docker Compose + Nginx 配置，详见 [阿里云部署步骤](docs/deploy-aliyun.md)。服务器安装 Docker/Compose 后，可在仓库根目录运行 `docker compose up -d --build`。

## 本地启动

终端一，从仓库根目录启动后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Windows PowerShell 激活命令为 `.venv\Scripts\Activate.ps1`。`requirements.txt` 记录直接依赖，`requirements.lock.txt` 固定运行时依赖版本。

终端二，从仓库根目录启动前端：

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev -- --hostname 127.0.0.1
```

- 页面：[http://localhost:3000](http://localhost:3000)
- 健康接口：[http://localhost:8000/api/health](http://localhost:8000/api/health)
- API 文档：[http://localhost:8000/docs](http://localhost:8000/docs)

浏览器通过 Next.js 的同源 `/api/*` 转发到 FastAPI，无需额外配置 CORS。修改 `frontend/.env.local` 中的 `BACKEND_URL` 后需重启前端，生产模式需重新构建。

云端预览时，把前端启动参数改为 `--hostname 0.0.0.0`，使用平台提供的 3000 端口转发地址。云端 localhost 不等于自己电脑的 localhost。

## 立即试用

1. 选择 `models/samples/box-10x20x30-mm.step`，点击“开始几何分析”。
2. 核对尺寸 **10 × 20 × 30 mm**、表面积 **2200 mm²**、体积 **6000 mm³**。
3. 旋转、缩放模型，点击“导出几何报告 JSON”。报告包含测量值、单位来源、质量提示和拓扑统计，不包含预览顶点数据。
4. 换成 `open-box-mm.stl` 并选择 mm：应显示网格不封闭，体积、重心不可用。

[样例说明](models/samples/README.md)列出更多预期结果和重新生成方式。

## 叶轮候选与工艺草案试用

1. 上传 `models/samples/synthetic-impeller-6-mm.step`，轴向选 Z。应得到 6 片候选、约 120 mm 径向包络直径、30 mm 总高及 9/9 采样一致证据。
2. 展开采样表，查看不同高度和半径的计数。表中弧长不是制造所需的真实壁厚/最小间隙。
3. 在工艺表单填写已确认的材料、机床、毛坯、最小流道宽度及 Vc/fz。预填机床与切削值为演示初值，不是针对所填材料的推荐。
4. 根部圆角或壁厚未知可留空；缺少圆角时不会生成精加工和清根参数。
5. 完成输入确认后生成草案，查看约束、刀具、公式、阻断项和待审核事项，导出参数包 JSON / 工序卡 CSV。
6. 修改任一输入后旧草案会清空。把机床改成三轴，重新生成应出现阻断项。普通圆柱不显示叶轮工艺表单。

生成样例用于识别算法验证，其直叶片和未圆角化根部不代表可制造产品。不要把测试代码中的假设工艺输入作为该样例的实测工程尺寸。

## 上传 API

`POST /api/analyze?filename=part.step&unit=mm&axis=Z` 使用原始文件字节作为请求体（非 multipart）。`unit` 仅影响 STL，`axis` 是叶轮候选识别的轴向（X/Y/Z，默认 Z）。

```bash
curl --fail-with-body \
  -H 'Content-Type: application/octet-stream' \
  --data-binary @models/samples/box-10x20x30-mm.step \
  'http://localhost:3000/api/analyze?filename=box.step' \
  -o geometry.json
```

- 上传上限 20 MiB；STL 上限 200,000 个三角面；STEP 上限 10,000 个拓扑面。
- 预览上限 100,000 个三角面，超过时保留测量结果并提示无法预览。
- 每个 API 进程最多两项上传/解析；解析子进程限时 45 秒。文件在请求结束后清理；不含预览网格的几何摘要最多保留 32 份、30 分钟供工艺接口使用。
- 当前使用进程内摘要缓存，请以单个 Uvicorn worker 运行；服务重启、缓存淘汰或过期后需要重新上传。
- 不支持格式返回 415，超出上传大小返回 413，空文件/损坏文件/超时返回 422，任务已满返回 503。

## 工艺 API

`POST /api/process-plan` 接收 JSON：`analysis_id` 必须来自本服务此前的分析，接口从缓存取几何数据，不接受客户端伪造的分析结果。完整输入字段见 [API 文档](http://localhost:8000/docs) 中的 `PlanRequest`。

要求人工确认零件族和工程输入，包含材料状态、机床轴数/尺寸限额/转速、圆柱毛坯、确认的最小流道宽度、可选的根部圆角和壁厚、Vc、fz、齿数和机时单价。过期分析返回 404；不适用模型或无效输入返回 422。几何约束或机床/刀具不匹配时仍可返回可审阅结果，但 `status=blocked`，估算时间/费用为空。

参数包保留文件 SHA-256、几何方法、识别证据、用户输入、规则版本、刀具假设、工序、计算依据及审核待办。完整几何测量值和单位来源另见几何报告。时间费用只计算理想连续粗加工场景，**不提供总节拍或完整报价**。

## 验证

后端（在 `backend/`）：

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

前端（在 `frontend/`）：

```bash
npm run lint
npm run build
npx tsc --noEmit
```

生产模式运行前端：构建后执行 `npm run start -- --hostname 127.0.0.1`；FastAPI 仍需独立运行。

## 适用边界

- STL 未做自交检查；有效性条件通过不等于完成制造级几何验证。不自动补洞、反转法向或更改几何来获得体积。
- STEP 多实体装配和带额外游离面的混合模型不输出体积、重心；面积仍按输入边界曲面统计，不是装配并集的外表面积。
- B-rep 无效时保留尺寸和面积供诊断，并明确提示；不输出体积、重心。
- 不支持 IGES。叶轮候选识别仅覆盖轴向对齐、近中心的周期径向薄片模型，不能视为通用语义分类器；分流叶片、偏心、任意姿态和复杂曲面尚未验证。
- 未确认的流道/壁厚/圆角不能由采样弧长替代。刀具库与 ap/ae 比例为演示规则；材料适配、真实刀具刀柄、工件刚度、碰撞、CAM 与后处理均待验证，不生成 NC 程序。
- 当前是本地 Demo，尚无用户认证、持久任务队列或公开部署所需的资源隔离。

后续路线见 [开发计划](docs/roadmap.md)。
