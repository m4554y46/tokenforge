\"\"\"Pytest fixtures for TokenForge Frontier Test Battery.\"\"\"

import os
import sys
import yaml
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

BATTERY_DIR = Path(__file__).parent


def load_all_categories():
    \"\"\"Load all prompt categories for pytest parametrization.\"\"\"
    categories = {
        \"00_legacy\": BATTERY_DIR / \"00_legacy\",
        \"01_compressibility\": BATTERY_DIR / \"01_compressibility.yaml\",
        \"02_structural\": BATTERY_DIR / \"02_structural.yaml\",
        \"03_semantic\": BATTERY_DIR / \"03_semantic.yaml\",
        \"04_adversarial\": BATTERY_DIR / \"04_adversarial.yaml\",
        \"05_domain\": BATTERY_DIR / \"05_domain.yaml\",
        \"06_crosslingual\": BATTERY_DIR / \"06_crosslingual.yaml\",
        \"07_ace_decision\": BATTERY_DIR / \"07_ace_decision.yaml\",
        \"08_regression\": BATTERY_DIR / \"08_regression.yaml\",
        \"09_calibration\": BATTERY_DIR / \"09_calibration.yaml\",
    }

    prompts = []
    for cat_name, cat_path in categories.items():
        if cat_path.is_dir():
            for yml_file in sorted(cat_path.glob(\"*.yaml\")):
                with open(yml_file, \"r\", encoding=\"utf-8\") as f:
                    data = yaml.safe_load(f)
                if not data:
                    continue
                outer_key = list(data.keys())[0]
                for pid, info in data[outer_key].get(\"prompts\", {}).items():
                    info[\"id\"] = pid
                    info[\"category\"] = cat_name
                    prompts.append(info)
        elif cat_path.exists():
            with open(cat_path, \"r\", encoding=\"utf-8\") as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            outer_key = list(data.keys())[0]
            cat_desc = data[outer_key].get(\"description\", \"\")
            for pid, info in data[outer_key].get(\"prompts\", {}).items():
                info[\"id\"] = pid
                info[\"category\"] = cat_name
                info[\"cat_description\"] = cat_desc
                prompts.append(info)

    return prompts


def pytest_generate_tests(metafunc):
    \"\"\"Parametrize tests with all prompts.\"\"\"
    if \"prompt_info\" in metafunc.fixturenames:
        prompts = load_all_categories()
        ids = [f\"{p['category']}/{p['id']}\" for p in prompts]
        metafunc.parametrize(\"prompt_info\", prompts, ids=ids)
