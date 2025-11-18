from dotenv import load_dotenv
import os
from pathlib import Path

# Load .env from the project root
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

def debug_env():
    print("ENV LOADED DEBUG:")
    print("LOGIN:", os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"))
    print("CUSTOMER:", os.getenv("GOOGLE_ADS_CUSTOMER_ID"))
    print("DEV TOKEN:", os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"))
    print("OPENAI:", os.getenv("OPENAI_API_KEY"))
