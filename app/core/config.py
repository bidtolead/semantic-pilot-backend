from dotenv import load_dotenv
import os
from pathlib import Path

# Load .env from the project root
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

# Stripe settings (will return None if not set yet)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO")  # price id for Pro plan
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_DUMMY_MODE = os.getenv("STRIPE_DUMMY_MODE", "false").lower() == "true"

