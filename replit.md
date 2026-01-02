# Gateway Monitor API

## Overview
This is a FastAPI-based application that monitors Stripe API changes automatically across multiple tiers (stable, preview, beta). It uses OpenAI for AI-powered change analysis and PostgreSQL for data persistence.

## Project Structure
```
app/
├── main.py              # FastAPI application entry point with all endpoints
├── config.py            # Application configuration using pydantic-settings
├── db/
│   └── database.py      # SQLAlchemy database configuration
├── models/
│   └── models.py        # SQLAlchemy models (Snapshot, Change, AlertSubscription)
├── services/
│   ├── ai_analyzer.py   # OpenAI-powered change analysis
│   ├── diff_engine.py   # Schema difference detection
│   ├── monitoring_service.py  # Main monitoring orchestration
│   └── stripe_crawler.py      # Stripe API specification crawler
└── scheduler/
    └── scheduler.py     # APScheduler for periodic monitoring
```

## Key Technologies
- **FastAPI**: Web framework for the REST API
- **SQLAlchemy**: ORM for PostgreSQL database
- **OpenAI**: AI-powered change analysis (using Replit AI Integrations)
- **APScheduler**: Background job scheduling for monitoring tasks
- **PostgreSQL**: Database for storing snapshots and changes

## Environment Variables
- `DATABASE_URL`: PostgreSQL connection string (auto-provided by Replit)
- `AI_INTEGRATIONS_OPENAI_API_KEY`: OpenAI API key (auto-provided by Replit AI Integrations)
- `AI_INTEGRATIONS_OPENAI_BASE_URL`: OpenAI base URL (auto-provided by Replit AI Integrations)

## API Endpoints
- `GET /`: Health check endpoint
- `POST /monitor/run`: Trigger monitoring for all tiers or specific tier
- `GET /monitor/compare`: Compare two tiers to see upcoming features
- `GET /snapshots`: Get recent snapshots
- `GET /changes`: Get recent changes with filtering
- `GET /changes/pipeline`: Get complete feature pipeline
- `POST /subscriptions`: Subscribe to email alerts

## Running the Application
The application runs on port 5000 using uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

## Recent Changes
- 2026-01-02: Imported from GitHub and configured for Replit environment
- Updated OpenAI integration to use Replit AI Integrations (gpt-5)
- Configured PostgreSQL database
- Set up workflow to run on port 5000
