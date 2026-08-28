# Intranet NL Report Generation Platform

Generate reports from your data with a single sentence of Chinese natural language. Employees upload an Excel file or select a database table; the platform parses their request with a local Ollama LLM and produces either an **aggregate report** or a **detail table (original columns + computed columns)**. All components run on the intranet — data never leaves.

> 中文文档：[README.md](README.md)

## Features

- 📊 **Two result types**: aggregate reports / detail tables with computed columns (e.g. conditional labels)
- 💬 **Natural language queries**: ask by business column names, no technical knowledge required
- 🔒 **Safe by design**: the LLM only outputs structured JSON intent; SQL is deterministically built by the backend after whitelist validation. Business databases are accessed **read-only**; writing new columns back to the source table requires admin approval
- 📁 **Multiple data sources**: Excel (.xlsx, multi-sheet, type inference) and PostgreSQL / MySQL / SQL Server via read-only accounts
- 📤 **Export**: preview first 100 rows, export full results to Excel / CSV (UTF-8 BOM, Excel-friendly)
- 📋 **Data dictionary**: maintain business names, dimension/measure roles and default aggregations online
- 🧾 **Audit log**: login, upload, parse, job, export, approval — fully traced
- ⚡ **Async jobs**: Celery + Redis (synchronous eager mode for development, no Redis needed)

## How It Works

```text
Upload Excel / connect DB → ask in natural language → Ollama parses intent to JSON
→ whitelist validation (table/column/agg/operator/expression) → preview result & SQL
→ user confirmation → Celery async job → result table → preview / export Excel
```

> Design principle: **the LLM never generates SQL directly**. SQL is built by deterministic code from validated JSON — safe and regression-testable.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | Vue 3 + Element Plus + Pinia + Vue Router + Axios |
| Backend | FastAPI + SQLAlchemy + Celery + DuckDB + pandas |
| LLM | Local Ollama models (Qwen2.5 / DeepSeek, etc.) |
| Storage | Metadata DB (PostgreSQL / SQLite), DuckDB result store |
| Deployment | Docker Compose (frontend / backend / worker / postgres / redis) |

## Quick Start

### Development (no Docker / Redis required)

```bash
# Backend
cd backend
python -m venv ../.venv
../.venv/Scripts/pip install -r requirements.txt   # Linux/macOS: ../.venv/bin/pip
../.venv/Scripts/python -m uvicorn app.main:app --reload

# Frontend (another terminal)
cd frontend
npm install
npm run dev    # http://localhost:5173, /api proxied to :8000
```

Default admin: `admin / admin123` (auto-seeded in dev; **change it before production**).

Run tests:

```bash
cd backend
../.venv/Scripts/python -m pytest -v    # 101 tests
```

### Production / Intranet Deployment

```bash
git clone https://github.com/CodeStar918/data-analysis.git
cd data-analysis
docker compose up -d --build
```

Five services: frontend / backend / celery worker / postgres / redis. For production you **must** change `JWT_SECRET`, `SECURITY_KEY` and the database password, and point `OLLAMA_BASE_URL` to your intranet Ollama instance. See the [Deployment Guide](docs/部署与操作手册.md) (Chinese, includes a go-live checklist).

## Example Requests

| Input | Result |
| --- | --- |
| “按区域和月份统计销售额合计，只看2024年” | Aggregate report: sales by region × month for 2024 |
| “给订单明细表增加一列：是否紧急，交货天数小于3且金额大于5000标记为紧急” | Detail table: original columns + `is_urgent` label column |

## Project Structure

```text
├── backend/               # FastAPI backend
│   └── app/
│       ├── api/           # auth / upload / datasource / metadata / nl_parse / job / result / approval / audit
│       ├── core/          # config / logging / security / crypto / celery
│       ├── models/        # SQLAlchemy models (user / datasource / metadata / job / approval / audit)
│       ├── schemas/       # Pydantic models
│       ├── services/      # Excel parsing / DuckDB / Ollama / NL validation / SQL builder / jobs / approval / audit
│       └── tests/         # 101 tests (incl. NL validation regression set)
├── frontend/              # Vue 3 app (login / datasources / metadata / workspace / results / approvals)
├── docs/                  # Design document / deployment guide (Chinese)
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Documentation

- [项目设计方案（设计文档）](docs/项目设计方案.md)
- [部署与操作手册（部署与运维指南）](docs/部署与操作手册.md)

## Branching Model

Simplified Git Flow: `master` is the release branch (tagged), `develop` for daily development, features via `feature/*` branches.

## License

[MIT](LICENSE)
