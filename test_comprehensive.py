import sys; sys.path.insert(0, '.')
from backend.prompt_optimizer import optimize_locally

prompts = [
    # User example
    "Si la température augmente et dépasse les 180°C, vous devez absolument couper le disjoncteur principal pour éviter une surchauffe.",
    # English conditional
    "If the temperature exceeds 180°C, you must immediately cut the main breaker to avoid overheating.",
    # Constraint
    "Write a summary in JSON format. The output must be under 200 words. Do not include any markdown formatting.",
    # French task
    "Je voudrais que tu analyses les données de vente Q4 par région dans un tableau comparatif.",
    # Simple context
    "We are building a React dashboard for tracking inventory across 12 warehouses in North America.",
]

for prompt in prompts:
    print("=" * 60)
    print(f"INPUT:  {prompt}")
    try:
        result = optimize_locally(prompt)
        for v in result:
            label = v['label']
            text = v['prompt']
            if label == 'Agressive':
                print(f"OUTPUT: {text}")
    except Exception as e:
        print(f"ERROR: {e}")
    print()
