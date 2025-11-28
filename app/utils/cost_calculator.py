"""
OpenAI API Cost Calculator
Prices as of November 2024
"""

# GPT-4o-mini pricing (per 1M tokens)
GPT4O_MINI_PRICING = {
    "prompt": 0.150,      # $0.150 per 1M input tokens
    "completion": 0.600,  # $0.600 per 1M output tokens
}

# GPT-4o pricing (per 1M tokens) - in case you upgrade
GPT4O_PRICING = {
    "prompt": 2.50,       # $2.50 per 1M input tokens
    "completion": 10.00,  # $10.00 per 1M output tokens
}

# GPT-4 Turbo pricing (per 1M tokens)
GPT4_TURBO_PRICING = {
    "prompt": 10.00,      # $10.00 per 1M input tokens
    "completion": 30.00,  # $30.00 per 1M output tokens
}

# GPT-3.5 Turbo pricing (per 1M tokens)
GPT35_TURBO_PRICING = {
    "prompt": 0.50,       # $0.50 per 1M input tokens
    "completion": 1.50,   # $1.50 per 1M output tokens
}


def get_model_pricing(model: str = "gpt-4o-mini") -> dict:
    """Get pricing for a specific model."""
    if model == "gpt-4o-mini":
        return GPT4O_MINI_PRICING
    elif model == "gpt-4o":
        return GPT4O_PRICING
    elif model == "gpt-4-turbo":
        return GPT4_TURBO_PRICING
    elif model == "gpt-3.5-turbo":
        return GPT35_TURBO_PRICING
    else:
        return GPT4O_MINI_PRICING


def get_cost_per_1k_tokens(model: str = "gpt-4o-mini") -> str:
    """
    Get the average cost per 1000 tokens for a model.
    Assumes a 50/50 split between prompt and completion tokens.
    
    Returns:
        Formatted string like "$0.000375"
    """
    pricing = get_model_pricing(model)
    
    # Average of prompt and completion (assuming 500 prompt + 500 completion = 1000 total)
    avg_cost_per_1k = ((pricing["prompt"] + pricing["completion"]) / 2) * (1000 / 1_000_000)
    
    return f"${avg_cost_per_1k:.6f}"


def calculate_openai_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str = "gpt-4o-mini"
) -> float:
    """
    Calculate the cost of an OpenAI API call.
    
    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        model: Model name (default: gpt-4o-mini)
    
    Returns:
        Cost in USD (as float)
    """
    
    pricing = get_model_pricing(model)
    
    # Calculate cost (convert from per-million to actual cost)
    prompt_cost = (prompt_tokens / 1_000_000) * pricing["prompt"]
    completion_cost = (completion_tokens / 1_000_000) * pricing["completion"]
    
    total_cost = prompt_cost + completion_cost
    
    return round(total_cost, 6)  # Round to 6 decimal places ($0.000001)


def format_cost(cost: float) -> str:
    """Format cost for display."""
    if cost < 0.01:
        return f"${cost:.6f}"
    else:
        return f"${cost:.4f}"
