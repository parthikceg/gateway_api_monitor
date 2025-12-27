import os
import pathlib

# Project structure
files = {
    ".gitignore": """# Python
__pycache__/
*.py[cod]
*$py.class
venv/
env/

# Environment
.env
.env.local

# Database
*.db
*.sqlite

# IDEs
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
""",

    "requirements.txt": """fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
pydantic==2.5.0
pydantic-settings==2.1.0
python-dotenv==1.0.0
httpx==0.25.2
openai==1.3.7
apscheduler==3.10.4
alembic==1.13.0
""",

    "Procfile": """web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
""",

    "railway.json": """{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
""",

    "README.md": """# Gateway Monitor Backend

Stripe API monitoring system with change detection.

## Deploy to Railway

1. Push to GitHub
2. Connect Railway to your repo
3. Add PostgreSQL database
4. Set environment variables
5. Deploy!

## Environment Variables
- `DATABASE_URL` - Auto-provided by Railway
- `OPENAI_API_KEY` - Your OpenAI key
""",

    "app/__init__.py": "",
    "app/models/__init__.py": "",
    "app/services/__init__.py": "",
    "app/scheduler/__init__.py": "",
    "app/db/__init__.py": "",
}

# Create all files and directories
for filepath, content in files.items():
    path = pathlib.Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    print(f"✅ Created {filepath}")

print("\n✅ Project structure created!")
print("\nNext: Run create_app_files.py to generate the application code")