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
- `app/models/models.py` - SQLAlchemy models (Snapshot, Change, AlertSubscription)

### Frontend (React/Vite)
- **Location**: `client/`
- **Port**: 5000 (0.0.0.0 for webview)
- **Framework**: React + Vite + Tailwind CSS
- **UI Components**: shadcn/ui

Key files:
- `client/src/App.tsx` - Main app with routing and navigation params
- `client/src/components/Layout.tsx` - Dashboard layout with sidebar
- `client/src/components/ChatWidget.tsx` - Floating AI chat widget (Intercom-style)
- `client/src/components/SubscribeModal.tsx` - Email subscription modal
- `client/src/pages/` - All dashboard pages
- `client/src/lib/api.ts` - API client
- `client/vite.config.ts` - Vite config with proxy

### Pages
1. **Dashboard** - Overview stats (clickable to filter), recent changes, API coverage
2. **Changes** - Filterable change history with severity badges
3. **Object Explorer** - Field hierarchy browser with "Ask AI" feature, beta/preview field highlighting
4. **Snapshots** - View all captured API snapshots with detail modal
5. **Compare** - Compare tiers (beta→stable, preview→stable, etc.)

## Features
- **Floating Chat Widget**: Intercom-style AI assistant at bottom-right corner
- **Clickable Stats**: Dashboard numbers link to filtered views
- **Tier Navigation**: Badge clicks navigate to Object Explorer with specific tier tab
- **Field Highlighting**: Beta-only and Preview-only fields are visually distinguished
- **Subscribe**: Email subscription for change alerts (stored in database)
- **AI SME**: Enhanced AI prompt acts as Senior Payments Expert

## API Endpoints

### Core
- `GET /` - Health check
- `GET /changes` - List changes (with filters: severity, tier, maturity)
- `GET /snapshots` - List snapshots (with filters: tier)
- `GET /snapshots/{id}` - Get snapshot detail with schema data
- `GET /snapshots/stats` - Snapshot statistics by tier
- `POST /monitor/run` - Trigger monitoring
- `GET /monitor/compare` - Compare tiers

### AI
- `POST /ai/ask` - AI-powered field insights (Payments SME)

### Subscriptions
- `POST /subscribe` - Subscribe to alerts (name, email)
- `GET /subscribers` - List all active subscribers

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

## Future Enhancements
- **Email Notifications**: To send email alerts to subscribers, set up Resend or SendGrid integration. The subscription data is stored in `alert_subscriptions` table.

## Recent Changes
- 2026-01-05: Modernized UI with gradient backgrounds, improved colors, card hover effects
- 2026-01-05: Added floating AI chat widget (Intercom-style)
- 2026-01-05: Made Dashboard stats clickable with filtered navigation
- 2026-01-05: Added Subscribe feature with modal UI and database storage
- 2026-01-05: Enhanced AI system prompt for Payments SME expertise
- 2026-01-05: Added beta/preview-only field highlighting in Object Explorer
- 2026-01-05: Added snapshot detail modal with JSON schema viewer
- 2026-01-02: Rebuilt frontend with professional dashboard UI
- 2026-01-02: Added AI-powered "Ask AI" feature for field insights
- 2026-01-02: Separated frontend/backend into dual workflow setup
