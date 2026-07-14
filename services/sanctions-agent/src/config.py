import os
from dotenv import load_dotenv

# Load local environment files if present
load_dotenv()

class Config:
    """Config skeleton to be populated with environment attributes."""
    OPENSANCTIONS_API_KEY = os.getenv("OPENSANCTIONS_API_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/techmkyc")
    PORT = int(os.getenv("PORT", 8001))
    HOST = os.getenv("HOST", "0.0.0.0")

settings = Config()
