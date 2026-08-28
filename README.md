# 企业内网自然语言报表生成平台

中文 | [English](README.en.md)

用一句中文，从已有数据生成报表。员工上传 Excel 或选择数据库表，系统借助本地 Ollama 大模型解析需求，自动生成**统计表**或**明细表（原字段 + 新增计算字段）**。全部组件部署于内网，数据不出内网。

## 功能特性

- 📊 **两类结果**：统计表（聚合汇总）/ 明细表（原字段 + 新增计算列，如条件标签列）
- 💬 **自然语言查询**：无需了解字段英文名，按业务名称提问，示例语句引导
- 🔒 **安全可控**：LLM 只解析意图输出 JSON，SQL 由后端白名单校验后确定性生成；业务库只读接入；写回原表需管理员审批
- 📁 **多数据源**：Excel（.xlsx 多 sheet / 类型推断）与 PostgreSQL / MySQL / SQL Server 等数据库
- 📤 **结果导出**：预览前 100 行，完整导出 Excel / CSV（utf-8-sig 中文无乱码）
- 📋 **数据字典**：字段业务名称、维度/度量、默认聚合在线维护（影响解析准确率）
- 🧾 **审计日志**：登录、上传、解析、任务、导出、审批全链路留痕
- ⚡ **异步任务**：Celery + Redis（开发模式可同步执行，无需 Redis）

## 核心流程

```text
上传 Excel / 接入数据库 → 输入一句话需求 → Ollama 解析为结构化 JSON
→ 白名单校验（表/字段/聚合/条件/表达式）→ 展示解析结果与 SQL 预览
→ 用户确认 → Celery 异步执行 → 结果表 → 预览 / 导出 Excel
```

> 设计原则：**大模型只解析意图，不直接生成 SQL**。SQL 由确定性代码根据校验后的 JSON 构建，安全且可回归测试。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Element Plus + Pinia + Vue Router + Axios |
| 后端 | FastAPI + SQLAlchemy + Celery + DuckDB + pandas |
| 模型 | Ollama 本地模型（Qwen2.5 / DeepSeek 等） |
| 存储 | 元数据库（PostgreSQL / SQLite）、DuckDB 结果库 |
| 部署 | Docker Compose（frontend / backend / worker / postgres / redis） |

## 快速开始

### 开发模式（无需 Docker / Redis）

```bash
# 后端
cd backend
python -m venv ../.venv
../.venv/Scripts/pip install -r requirements.txt   # Linux/macOS: ../.venv/bin/pip
../.venv/Scripts/python -m uvicorn app.main:app --reload

# 前端（另开终端）
cd frontend
npm install
npm run dev    # http://localhost:5173，/api 自动代理到 8000
```

默认管理员：`admin / admin123`（开发库自动初始化，**上线前务必修改**）。

运行测试：

```bash
cd backend
../.venv/Scripts/python -m pytest -v    # 101 个测试
```

### Docker Compose 部署（生产/内网）

```bash
git clone https://github.com/CodeStar918/data-analysis.git
cd data-analysis
docker compose up -d --build
```

包含 frontend / backend / celery worker / postgres / redis 五个服务。生产环境**必须修改** `JWT_SECRET`、`SECURITY_KEY`、数据库密码，并配置 `OLLAMA_BASE_URL` 指向内网 Ollama 服务。详见 [部署与操作手册](docs/部署与操作手册.md)（含上线检查清单）。

## 使用示例

| 输入 | 结果 |
| --- | --- |
| “按区域和月份统计销售额合计，只看2024年” | 统计表：区域 × 月份的销售额汇总 |
| “给订单明细表增加一列：是否紧急，交货天数小于3且金额大于5000标记为紧急” | 明细结果表：原字段 + `is_urgent` 条件标签列 |

## 项目结构

```text
├── backend/               # FastAPI 后端
│   └── app/
│       ├── api/           # auth / upload / datasource / metadata / nl_parse / job / result / approval / audit
│       ├── core/          # 配置 / 日志 / 安全 / 加密 / Celery
│       ├── models/        # SQLAlchemy 模型（用户/数据源/元数据/任务/审批/审计）
│       ├── schemas/       # Pydantic 模型
│       ├── services/      # Excel 解析 / DuckDB / Ollama / NL 校验 / SQL 构建 / 任务 / 审批 / 审计
│       └── tests/         # 101 个测试（含 NL 校验回归语句集）
├── frontend/              # Vue 3 前端（登录 / 数据源 / 元数据 / 工作台 / 结果中心 / 审批）
├── docs/                  # 设计方案 / 部署与操作手册
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## 文档

- [项目设计方案](docs/项目设计方案.md) —— 架构、核心流程、分阶段实施计划
- [部署与操作手册](docs/部署与操作手册.md) —— 部署步骤、配置项、故障排查、上线检查清单

## 分支模型

Git Flow 简化版：`master` 发布（打 tag），`develop` 日常开发，功能走 `feature/*` 分支。
