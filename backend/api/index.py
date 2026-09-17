from mangum import Mangum
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app

handler = Mangum(app)
