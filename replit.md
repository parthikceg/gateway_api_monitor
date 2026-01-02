# Gateway Monitor - Stripe API Change Tracker

## Overview
A professional full-stack application to monitor Stripe API changes across multiple tiers (stable, preview, beta). The system captures API snapshots, detects changes, provides AI-powered analysis, and offers a comprehensive web dashboard.

## Project Architecture

### Backend (Python/FastAPI)
- **Location**: `app/`
- **Port**: 8000 (localhost)
- **Framework**: FastAPI with SQLAlchemy ORM
- **Database**: PostgreSQL (Replit-managed)
- **AI**: OpenAI integration via Replit AI Integrations (gpt-5 model)

Key files:
- `app/main.py` - Main FastAPI application with all endpoints
- `app/config.py` - Configuration settings
- `app/db/` - Database models and connection
- `app/services/` - Business logic services

### Frontend (React/Vite)
- **Location**: `client/`
- **Port**: 5000 (0.0.0.0 for webview)
- **Framework**: React + Vite + Tailwind CSS
- **UI Components**: shadcn/ui

Key files:
- `client/src/App.tsx` - Main app with routing
- `client/src/components/Layout.tsx` - Dashboard layout
- `client/src/pages/` - All dashboard pages
- `client/src/lib/api.ts` - API client
- `client/vite.config.ts` - Vite config with proxy

### Pages
1. **Dashboard** - Overview stats, recent changes, API coverage
2. **Changes** - Filterable change history with severity badges
3. **Object Explorer** - Field hierarchy browser with "Ask AI" feature
4. **Snapshots** - View all captured API snapshots
5. **Compare** - Compare tiers (beta→stable, preview→stable, etc.)

## API Endpoints

### Core
- `GET /` - Health check
- `GET /changes` - List changes (with filters)
- `GET /snapshots` - List snapshots
- `GET /snapshots/{id}` - Get snapshot detail
- `GET /snapshots/stats` - Snapshot statistics
- `POST /monitor/run` - Trigger monitoring
- `GET /monitor/compare` - Compare tiers
- `POST /ai/ask` - AI-powered field insights

## Running the Application

### Development
Two workflows run simultaneously:
1. **Backend API**: `uvicorn app.main:app --host localhost --port 8000`
2. **Frontend**: `cd client && npm run dev` (port 5000)

Frontend proxies `/api` requests to backend via Vite config.

## Technology Stack
- Python 3.11, FastAPI, SQLAlchemy, APScheduler
- React 19, Vite, Tailwind CSS v4, shadcn/ui
- PostgreSQL, OpenAI (via Replit AI Integrations)

## Recent Changes
- 2026-01-02: Rebuilt frontend with professional dashboard UI
- 2026-01-02: Added AI-powered "Ask AI" feature for field insights
- 2026-01-02: Separated frontend/backend into dual workflow setup
