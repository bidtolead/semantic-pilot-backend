from dotenv import load_dotenv
import os
from pathlib import Path

# Load .env from the project root
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

def debug_env():
    """Print limited env diagnostics (non-production only)."""
    if os.getenv("ENVIRONMENT") == "production":
        return
    print("ENV LOADED DEBUG:")
    masked = lambda v: "SET" if v else "MISSING"
    print("LOGIN:", masked(os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")))
    print("CUSTOMER:", masked(os.getenv("GOOGLE_ADS_CUSTOMER_ID")))
    print("DEV TOKEN:", masked(os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")))
    print("OPENAI:", masked(os.getenv("OPENAI_API_KEY")))
