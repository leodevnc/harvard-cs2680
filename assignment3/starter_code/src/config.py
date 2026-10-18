import os


def settings():
    return {
        'base_url': os.environ['CS2680_BASE_URL'],
        'api_key': os.environ['CS2680_API_KEY'],
        'standard': os.environ.get('CS2680_MODEL_STANDARD', 'standard'),
        'expert': os.environ.get('CS2680_MODEL_EXPERT', 'expert'),
        'starter': os.environ.get('CS2680_MODEL_STARTER', 'starter'),
        'max_attempts': int(os.environ.get('CS2680_MAX_ATTEMPTS', '2')),
        'workers': min(5, max(1, int(os.environ.get('CS2680_WORKERS', '2')))),
        'budget_usd': float(os.environ.get('CS2680_HARNESS_BUDGET', '8')),
    }
