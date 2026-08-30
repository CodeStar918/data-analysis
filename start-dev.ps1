# 一键启动开发环境：后端 FastAPI(8000) + 前端 Vite(5173)
# 用法：
#   .\start-dev.ps1            # 启动前后端（两个独立窗口）并打开浏览器
#   .\start-dev.ps1 -mode backend    # 仅启动后端
#   .\start-dev.ps1 -mode frontend   # 仅启动前端
param([string]$mode = "all")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Start-Backend {
    Write-Host "[后端] FastAPI 启动中: http://localhost:8000 (文档 /docs)" -ForegroundColor Cyan
    Push-Location "$root\backend"
    & "$root\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
    Pop-Location
}

function Start-Frontend {
    Write-Host "[前端] Vite 启动中: http://localhost:5173" -ForegroundColor Cyan
    Push-Location "$root\frontend"
    npm run dev
    Pop-Location
}

# ---- 子模式：在独立窗口中运行 ----
if ($mode -eq "backend") { Start-Backend; exit }
if ($mode -eq "frontend") { Start-Frontend; exit }

# ---- 首次运行环境检查 ----
if (-not (Test-Path "$root\backend\.env")) {
    Copy-Item "$root\backend\.env.example" "$root\backend\.env"
    Write-Host "已从 .env.example 生成 backend\.env，按需修改后重启即可" -ForegroundColor Yellow
}

if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    Write-Host "未找到 .venv，正在创建虚拟环境..." -ForegroundColor Yellow
    python -m venv "$root\.venv"
    & "$root\.venv\Scripts\pip.exe" install -i https://pypi.org/simple -r "$root\backend\requirements.txt"
}

if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "未找到前端依赖，正在 npm install..." -ForegroundColor Yellow
    Push-Location "$root\frontend"
    npm install
    Pop-Location
}

# ---- 启动前后端（各一个独立窗口，关闭窗口即停止对应服务）----
$self = $MyInvocation.MyCommand.Path
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$self`"", "-mode", "backend"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$self`"", "-mode", "frontend"

# 等服务起来后打开浏览器
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "已启动：后端窗口(8000) + 前端窗口(5173)，浏览器已打开 http://localhost:5173" -ForegroundColor Green
Write-Host "停止服务：关闭对应窗口即可（后端 --reload 会自动重载代码）"
