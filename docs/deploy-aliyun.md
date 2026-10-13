# 阿里云 ECS 公网演示部署

本配置运行 Next.js、FastAPI 和 Nginx，公网只开放 Nginx 的一个 HTTP 端口。它不会自动购买 ECS、分配公网 IP 或修改阿里云安全组。

## 1. 服务器准备

推荐 **x86_64、Ubuntu 22.04/24.04、2 核 8 GB 内存、至少 20 GB 空闲磁盘**，并配置公网 IPv4/EIP 和公网带宽。首次编译与 OpenCascade 依赖下载会占用较多内存和时间。小规格服务器可先在其他机器构建镜像再传入。

在阿里云 ECS 控制台：

- 查看实例的公网 IP；没有公网 IP 时需分配 EIP 或配置公网网络。
- 安全组允许 TCP **80** 入站，供所有人访问演示；SSH 22 仅对自己的管理 IP 开放。
- 不需要向公网开放 3000 或 8000。
- 如服务器启用了 UFW 等系统防火墙，同样允许 80；保留当前 SSH 访问规则。

安装 Git、Docker Engine 和 Docker Compose v2。Docker 安装请按官方 Ubuntu 文档操作：[Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)。完成后确认：

```bash
git --version
docker version
docker compose version
```

普通用户若没有 Docker 权限，可在下文 Docker 命令前加 `sudo`。

## 2. 拉取代码并启动

```bash
git clone https://github.com/bung12atron3690-crypto/impeller-process-demo.git
cd impeller-process-demo
git checkout main
docker compose up -d --build
```

若仓库为私有，请在服务器使用 GitHub 授权的 SSH key 或凭据管理器；不要把访问令牌写进部署配置或分享命令中。

首次构建需要访问 Docker Hub、npm、PyPI 和 Debian 软件源。如果下载失败，检查 ECS 网络和对应源的可达性；使用可信镜像源时保持版本锁定与校验，不要关闭 TLS 校验。

```bash
docker compose ps
curl --fail http://127.0.0.1/api/health
```

三个服务应为 running/healthy，健康接口返回 `{"status":"ok","service":"impeller-process-demo"}`。

然后用自己电脑的浏览器打开：

```text
http://你的ECS公网IP/
```

这就是可以发给其他人访问的演示地址。仓库地址是代码地址，不能替代服务器运行后的网页地址。

## 3. 下载演示模型

部署成功后，可从以下地址下载模型，再在首页选择文件上传：

```text
http://你的ECS公网IP/samples/synthetic-impeller-6-mm.step
http://你的ECS公网IP/samples/synthetic-impeller-7-mm.step
http://你的ECS公网IP/samples/box-10x20x30-mm.step
```

叶轮样例选择 Z 轴。生成的直叶片样例用于演示识别流程，工艺输入需独立确认，不能把草案直接上机。

## 4. 更新、日志与停止

更新：

```bash
git pull --ff-only origin main
docker compose up -d --build --force-recreate
```

强制重建容器可以保证 Nginx 使用当前后端地址。更新/重启会清空内存中的分析摘要，重新上传模型即可。

查看日志：

```bash
docker compose logs --tail=100 gateway frontend backend
```

停止服务：

```bash
docker compose down
```

端口 80 被占用时，可临时选择 8080：

```bash
DEMO_PORT=8080 docker compose up -d --build
```

此时安全组放行 8080，访问 `http://公网IP:8080/`。以后启动/更新也要保持同一个 `DEMO_PORT`。

## 5. 运行边界与排查

- `backend` 必须保持一个进程/一个副本，当前分析摘要缓存没有共享数据库；摘要最多保留 30 分钟、32 份。
- 上传上限 20 MiB、同时最多两项分析、每项解析最长 45 秒。Nginx 对同一来源 IP 的分析请求限制为每分钟 6 次（允许少量突发）。忙碌或限流时请稍后重试。
- 容器已设置内存/进程数约束，后端临时上传目录不持久化；这仍是公开演示配置，不是生产多租户服务。
- 本地健康接口成功而公网无法打开：核对 EIP/公网带宽、安全组、系统防火墙和实际端口。
- 502/服务不健康：先看 `docker compose ps` 和日志；确认后端依赖安装成功，服务器没有内存不足。
- 404 分析已过期：重新上传文件。
- 当前 IP 直连使用 HTTP，演示时使用公开或非敏感样件。需要 HTTPS 时再配置域名、证书和对应云平台接入要求。
