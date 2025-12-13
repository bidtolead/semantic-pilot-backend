# app/core/env.py

import os
from dotenv import load_dotenv


def _select_env_path() -> str:
	"""Pick .env file based on ENV flag to support staging/production splits."""
	base_dir = os.path.join(os.path.dirname(__file__), "..", "..")
	env_name = os.getenv("ENV", "local").lower()

	if env_name == "staging":
		candidate = os.path.join(base_dir, ".env.staging")
	elif env_name in {"prod", "production"}:
		candidate = os.path.join(base_dir, ".env.production")
	else:
		candidate = os.path.join(base_dir, ".env")

	return candidate


env_path = _select_env_path()
load_dotenv(env_path)
