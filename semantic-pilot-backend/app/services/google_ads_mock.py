import random

def mock_keyword_results(seed_keywords: list):
    fake_data = []

    for kw in seed_keywords:
        for i in range(3):
            fake_term = f"{kw} idea {i+1}"
            fake_data.append({
                "keyword": fake_term,
                "avg_monthly_searches": random.randint(50, 5000),
                "competition": random.choice(["LOW", "MEDIUM", "HIGH"]),
                "cpc": round(random.uniform(0.3, 4.5), 2)
            })

    return fake_data
