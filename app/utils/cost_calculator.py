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
    
    # Select pricing based on model
    if model == "gpt-4o-mini":
        pricing = GPT4O_MINI_PRICING
    elif model == "gpt-4o":
        pricing = GPT4O_PRICING
    else:
        # Default to gpt-4o-mini pricing
        pricing = GPT4O_MINI_PRICING
    
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
