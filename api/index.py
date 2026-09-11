from mangum import Mangum
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app

# Mangum wraps FastAPI for AWS Lambda / Vercel serverless
handler = Mangum(app)
