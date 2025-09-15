#!/bin/bash
echo "🚀 Starting ClaimSafer with authentication system..."
python3 setup_production_db.py
echo "✅ Database setup complete"
uvicorn main:app --host 0.0.0.0 --port $PORT