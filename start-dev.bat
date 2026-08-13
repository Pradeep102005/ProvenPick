@echo off
title ProvenPick Local Dev Launcher

echo ========================================================
echo 🚀 STARTING PROVENPICK LOCAL DEVELOPER ENVIRONMENT
echo ========================================================

set PRODUCTION_DATABASE_URL=sqlite:///c:/Users/prade/Desktop/ProvenPick/provenpick_production.db
set STAGING_DATABASE_URL=sqlite:///c:/Users/prade/Desktop/ProvenPick/provenpick_staging.db

echo Starting Production API on http://localhost:8002...
start "ProvenPick Production API (8002)" cmd /k "cd production-api && set PYTHONPATH=. && python -m uvicorn src.main:app --port 8002 --reload"

echo Starting Staging API on http://localhost:8001...
start "ProvenPick Staging API (8001)" cmd /k "cd staging-api && set PYTHONPATH=. && python -m uvicorn src.main:app --port 8001 --reload"

echo Starting Public Site Frontend on http://localhost:3000...
start "ProvenPick Public Site (3000)" cmd /k "cd public-site && npm run dev"

echo Starting Editor Dashboard Frontend on http://localhost:3001...
start "ProvenPick Editor Dashboard (3001)" cmd /k "cd editor-dashboard && npm run dev"

echo ========================================================
echo ✅ Local environment launched!
echo Public Site: http://localhost:3000
echo Editor Dashboard: http://localhost:3001
echo ========================================================
