@echo off
title ProvenPick Local Dev Launcher

echo ========================================================
echo 🚀 STARTING PROVENPICK LOCAL DEVELOPER ENVIRONMENT
echo ========================================================

set PRODUCTION_DATABASE_URL=sqlite:///c:/Users/prade/Desktop/ProvenPick/provenpick_production.db
set STAGING_DATABASE_URL=sqlite:///c:/Users/prade/Desktop/ProvenPick/provenpick_staging.db

echo Starting Production API on http://localhost:8002...
start "ProvenPick Production API" cmd /k "cd /d %~dp0production-api && set PYTHONPATH=. && python -m uvicorn src.main:app --port 8002"

echo Starting Staging API on http://localhost:8001...
start "ProvenPick Staging API" cmd /k "cd /d %~dp0staging-api && set PYTHONPATH=. && python -m uvicorn src.main:app --port 8001"

echo Starting Public Site Frontend on http://localhost:3000...
start "ProvenPick Public Site" cmd /k "cd /d %~dp0public-site && npm run dev"

echo Starting Editor Dashboard Frontend on http://localhost:3001...
start "ProvenPick Editor Dashboard" cmd /k "cd /d %~dp0editor-dashboard && npm run dev"

timeout /t 3 /nobreak >nul

echo Opening browser tabs...
start http://localhost:3000
start http://localhost:3001

echo ========================================================
echo ✅ Local environment launched!
echo Public Site: http://localhost:3000
echo Editor Dashboard: http://localhost:3001
echo ========================================================
