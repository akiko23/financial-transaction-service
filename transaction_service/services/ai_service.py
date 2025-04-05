import asyncio
import random

# model = load_model()
def analyze_text() -> dict:
    category = random.choice(['Misc', 'Transport', 'Food', 'Shopping', 'Rent'])
    return {
        "category": category,
    }
