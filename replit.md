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

Access interactive API docs at `/api/docs` (Swagger UI) or `/api/redoc` (ReDoc).

### Health Check
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Returns service health status, version, and supported tiers |

### Monitoring
| Method | Endpoint | Description | When to Use |
|--------|----------|-------------|-------------|
| POST | `/monitor/run` | Trigger API monitoring for all tiers or a specific tier | Run manually to capture latest Stripe API specs and detect changes |
| POST | `/monitor/run?tier=beta` | Monitor only the beta tier | When you need to refresh a specific tier's snapshot |
| GET | `/monitor/compare` | Compare two tiers to see upcoming features | See what's in beta/preview that isn't yet in stable |

**Compare endpoint query params:**
- `source`: Required. Either `preview` or `beta`
- `target`: Optional. Either `stable` or `preview` (default: `stable`)

### Changes
| Method | Endpoint | Description | When to Use |
|--------|----------|-------------|-------------|
| GET | `/changes` | List detected API changes with filtering | View change history, filter by severity/tier |

**Query params:**
- `limit`: Number of results (default: 20)
- `severity`: Filter by `high`, `medium`, `low`, or `info`
- `tier`: Filter by `stable`, `preview`, or `beta`
- `maturity`: Filter by change maturity level

### Snapshots
| Method | Endpoint | Description | When to Use |
|--------|----------|-------------|-------------|
| GET | `/snapshots` | List captured API snapshots | View all historical snapshots |
| GET | `/snapshots/{id}` | Get full snapshot details with JSON schema | Inspect complete API schema for a snapshot |
| GET | `/snapshots/stats` | Get snapshot counts by tier | Dashboard statistics |

**Query params for list:**
- `limit`: Number of results (default: 10)
- `tier`: Filter by `stable`, `preview`, or `beta`

### AI Assistant
| Method | Endpoint | Description | When to Use |
|--------|----------|-------------|-------------|
| POST | `/ai/ask` | Ask the AI about API fields or changes | Get expert explanations of Stripe API concepts |

**Request body:**
```json
{
  "question": "What is this field used for?",
  "context": {
    "field": { "name": "amount", "type": "integer", "tier": "stable" },
    "conversationHistory": []
  }
}
```

### Subscriptions
| Method | Endpoint | Description | When to Use |
|--------|----------|-------------|-------------|
| POST | `/subscribe` | Subscribe to API change alerts | Register email for notifications |
| GET | `/subscribers` | List all active subscribers | Admin view of subscriptions |

**Request body for subscribe:**
```json
{
  "name": "John Doe",
  "email": "john@example.com"
}
```

### Testing (Development Only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/monitor/inject-test-snapshot` | Create a modified snapshot for testing change detection |

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
- 2026-01-07: Removed 8 unused API endpoints (debug endpoints, duplicates, unused features)
- 2026-01-07: Updated API documentation with comprehensive endpoint reference
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
