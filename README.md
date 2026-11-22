# Openlist-Ani-webui

现代化、安全可部署的 [Openlist-Ani](https://github.com/TwooSix/Openlist-Ani) Web 管理控制台，专为 **1Panel + OpenList + PikPak + Openlist-Ani + Jellyfin** 自托管番剧自动化工作流设计。

本项目不修改、也不重复实现 Openlist-Ani 的核心下载与番剧识别引擎，而是通过 **FastAPI 安全反向代理 + Vue 3 现代前端**，严格按照 Openlist-Ani 官方真实 HTTP 接口提供登录认证、磁力/种子解析、策略冲突预检确认、任务监控、番剧识别结果查看及系统设置能力。

---

## 核心特性

- **安全反代架构**：Openlist-Ani 内部地址仅存储在 WebUI 服务端，浏览器仅访问 WebUI 自身后端，不直接暴露内部端口或地址。
- **完整安全防护**：服务端持久化会话（SQLite + SHA-256 令牌哈希）、`HttpOnly` + `SameSite=Lax` Cookie、会话绑定 `X-CSRF-Token` 与 `Origin` 校验、基于 IP 的登录失败限流、严格 API 白名单（禁止任意 URL 代理，明确排除 `/api/restart` 等管理接口）。
- **手动添加下载全流程**：
  - 支持粘贴 `magnet:?` 磁力链接或 `http(s)://` `.torrent` 链接并自动识别类型
  - 调用 `POST /api/resolve_magnet` / `POST /api/resolve_torrent` 解析真实标题与种子内文件列表
  - 依据官方视频扩展名规则自动判断单集或合集（`collection_hint`），元数据不完整时保守提示
  - 无法解析标题时要求用户手动填写，绝不伪造番剧名称
  - 提交前强制调用 `POST /api/downloads/preflight` 检查策略冲突；若需确认，完整展示所有冲突键、原因与命中项并经用户勾选确认后再提交 `POST /api/downloads`
- **真实任务监控**：
  - 通过 `GET /api/downloads` 与 `GET /api/downloads/{task_id}` 每 5 秒自动轮询（后台标签页自动暂停，支持手动刷新与按任务 ID 查询历史任务）
  - 展示 Openlist-Ani 真实工作流阶段（`pending` / `downloading` / `downloaded` / `resolving` / `renaming` / `renamed` / `notifying` / `completed` / `failed` / `cancelled`），不捏造进度百分比，不虚构官方未提供的取消/删除按钮
  - 支持卡片视图与列表视图切换、搜索、状态筛选、排序与单文件明细抽屉
- **番剧识别结果 & 仪表盘**：原样展示 Openlist-Ani 返回的番剧名、季/集、字幕组、清晰度、处理结果、最终路径、服务健康探针与最近错误，绝不使用假数据。
- **现代响应式界面**：默认深色模式、支持浅色模式、简体中文默认（支持切换英文），完美适配桌面端与 iPhone / Android 移动端。

---

## 对接的 Openlist-Ani 官方真实接口

经核对 `TwooSix/Openlist-Ani` 源码（`src/openlist_ani/adapters/http/router.py`、`schemas.py`、`app.py`），本 WebUI **仅代理以下白名单接口**：

| Openlist-Ani 接口 | WebUI 后端代理路由 | 用途 |
|---|---|---|
| `GET /health/live` & `GET /health/ready` | `GET /api/v1/health` | 检测上游连通性、就绪状态与后台工作线程数 |
| `POST /api/resolve_magnet` | `POST /api/v1/resolve/magnet` | 解析磁力链接标题、种子文件列表与合集判定 |
| `POST /api/resolve_torrent` | `POST /api/v1/resolve/torrent` | 下载并解析 `.torrent` 链接标题与文件列表 |
| `POST /api/downloads/preflight` | `POST /api/v1/downloads/preflight` | 只读策略预检，返回冲突项与 `policy_review_token` |
| `POST /api/downloads` | `POST /api/v1/downloads` | 提交手动下载任务（必填 `title`） |
| `GET /api/downloads` | `GET /api/v1/downloads` | 获取当前活动与失败任务列表 |
| `GET /api/downloads/{task_id}` | `GET /api/v1/downloads/{task_id}` | 获取单任务完整状态、单文件结果及已完成任务最终路径 |

> **安全边界说明**：Openlist-Ani 的 `POST /api/restart` 等管理控制接口**不会被代理**；WebUI 后端不存在通用路径转发器，从结构上杜绝 SSRF 与未授权管理操作。

---

## 项目目录结构

```text
Openlist-Ani-webui/
├── Dockerfile                  # 多阶段构建（Node 22 + Python 3.12），兼容 AMD64 / ARM64
├── docker-compose.yml          # 兼容 1Panel V2 与标准 Docker Compose
├── .env.example                # 环境变量配置模板
├── .github/workflows/ci.yml    # 后端测试、前端类型检查/单测/构建、多架构镜像验证
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # FastAPI 应用工厂、安全响应头、统一异常处理、SPA 静态托管
│   │   ├── config.py           # 环境变量解析与启动安全校验
│   │   ├── security.py         # scrypt 密码哈希、会话哈希、CSRF、SSRF URL 校验、登录限流
│   │   ├── storage.py          # SQLite 持久化（会话、服务端设置、观测任务 ID 跟踪）
│   │   ├── schemas.py          # 严格匹配 Openlist-Ani 响应的 Pydantic v2 模型
│   │   ├── upstream.py         # 白名单 httpx 客户端与统一错误封装
│   │   ├── dependencies.py     # 会话鉴权与 CSRF 依赖注入
│   │   └── routers/
│   │       ├── auth.py         # 登录 / 登出 / 当前会话
│   │       ├── health.py       # 容器探针与上游健康检查
│   │       ├── downloads.py    # 解析 / 预检 / 创建 / 列表 / 单任务详情
│   │       └── settings.py     # 服务端设置与安全连接测试
│   └── tests/                  # pytest 单元测试与 Openlist-Ani Mock 测试
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── vitest.config.ts
    └── src/
        ├── types/api.ts        # 严格 TypeScript API 类型定义
        ├── api/client.ts       # Fetch 封装（Cookie 会话 + X-CSRF-Token）
        ├── stores/             # Pinia 状态管理（auth / downloads / health / settings）
        ├── utils/              # 状态映射、体积/时间格式化、磁力/合集工具
        ├── i18n/               # 简体中文（默认）/ English 文案
        ├── components/         # 布局壳层、新建下载弹窗、任务卡片/列表/详情抽屉
        ├── views/              # 登录、仪表盘、下载管理、番剧识别、系统设置
        └── __tests__/          # Vitest 单元测试与核心流程组件测试
```

---

## 快速部署（Docker Compose / 1Panel V2）

### 1. 准备环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少修改以下两项：

- `OPENLIST_ANI_URL`：指向 Openlist-Ani 内部地址（例如宿主机运行填 `http://host.docker.internal:26666`，同 Docker 网络填 `http://openlist-ani:26666`）。
- `WEBUI_PASSWORD` 或 `WEBUI_PASSWORD_HASH`：管理员密码（**未配置时后端将拒绝启动**，防止弱口令暴露）。

推荐使用哈希密码替代明文密码：

```bash
docker build -t openlist-ani-webui:latest .
docker run --rm openlist-ani-webui:latest python -m app.security hash-password '你的高强度密码'
```

将输出的 `scrypt$...` 填入 `.env` 的 `WEBUI_PASSWORD_HASH`，并清空 `WEBUI_PASSWORD`。

### 2. 启动容器

```bash
docker compose up -d --build
```

默认仅绑定宿主机 `127.0.0.1:8080`（可通过 `.env` 中的 `WEBUI_BIND_IP` 和 `WEBUI_EXPOSE_PORT` 调整）。

### 3. 1Panel V2 部署建议

1. 在 1Panel V2 的 **容器 → 编排** 中导入本仓库的 `docker-compose.yml` 与 `.env`。
2. 如 Openlist-Ani 与本服务均位于 `1panel-network` 网络中，取消 `docker-compose.yml` 中 `1panel-network` 注释，并将 `OPENLIST_ANI_URL` 设为 `http://openlist-ani:26666`（容器名需与您的 Openlist-Ani 容器一致）。
3. 在 1Panel V2 **网站 → 反向代理** 中新建站点并启用 HTTPS，将代理目标指向 `http://127.0.0.1:8080`，保持 `.env` 中 `WEBUI_TRUST_PROXY=true` 和 `WEBUI_COOKIE_SECURE=auto`，即可自动获得 HTTPS `Secure` Cookie 与真实客户端 IP 登录限流。
4. 切勿在 1Panel 或路由器中直接将 Openlist-Ani 的 `26666` 端口映射到公网。

### 多架构构建（AMD64 & ARM64）

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t openlist-ani-webui:latest \
  .
```

---

## 本地开发与测试

### 后端（Python 3.12 + FastAPI）

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 运行单元测试与 API Mock 测试
pytest -v

# 本地启动后端开发服务
export WEBUI_USERNAME=admin
export WEBUI_PASSWORD='dev-password-123'
export OPENLIST_ANI_URL='http://127.0.0.1:26666'
uvicorn app.main:get_asgi_app --factory --reload --port 8080
```

### 前端（Vue 3 + TypeScript + Vite）

```bash
cd frontend
npm install

# 运行 Vitest 单测与组件测试
npm run test

# 严格 TypeScript 检查与生产构建
npm run build

# 启动前端开发服务器（自动代理 /api 到 127.0.0.1:8080）
npm run dev
```

---

## 开源协议

基于 [MIT License](LICENSE) 开源。
