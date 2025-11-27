from dotenv import load_dotenv
import os
from pathlib import Path

# Load .env from the project root
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

