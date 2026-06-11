# Rapport de Test — Template
# GÃ©nÃ©rÃ© par run_battery.py — ne pas Ã©diter manuellement

## MÃ©ta

- Date : {{DATE}}
- Version batterie : 1.0
- Mode : {{MODE}} (all/legacy/ci/category)
- Seuils : tests/prompts/thresholds.yaml

## RÃ©sumÃ©

| MÃ©trique | Valeur |
|-----------|--------|
| Total prompts | {{TOTAL}} |
| PASS | {{PASS}} |
| FAIL | {{FAIL}} |
| Taux de rÃ©ussite | {{RATE}}% |

## RÃ©sultats par catÃ©gorie

{{CATEGORY_TABLE}}

## DÃ©tails des Ã©checs

{{FAILURE_DETAILS}}

## Prompts sans erreur (succÃ¨s partiel)

{{PARTIAL_SUCCESS}}

## Note sur les seuils

Les seuils utilisÃ©s pour ce rapport sont dÃ©finis dans 	hresholds.yaml.
Les valeurs clÃ©s :
- FrontiÃ¨re cold-start : ~1200 tokens
- Bypass systÃ©matique : < 50 tokens
- QualitÃ© minimale : 0.80
- MIN_CLIENT_SAVINGS : .001
