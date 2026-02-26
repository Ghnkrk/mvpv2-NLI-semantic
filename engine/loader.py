import json


def load_rules(path: str) -> dict:
    """Load rules from a JSON file and return as a structured dict."""
    with open(path, 'r') as f:
        rules = json.load(f)
    return rules
