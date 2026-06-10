"""Quality Judge — évaluation automatique de la qualité par GPT-4o.

Compare la réponse compressée à la réponse de référence (non compressée)
et produit un score de qualité (0.0 à 1.0) qui sert de pseudo-label
pour l'entraînement du modèle de qualité ACE.

Usage:
    judge = QualityJudge(api_key="sk-...")
    score = judge.evaluate(prompt, compressed_response, reference_response)
    # score = 0.95 → qualité quasi préservée
    # score = 0.30 → qualité très dégradée

Le juge peut fonctionner :
- Online : évalue chaque réponse compressée en temps réel
- Offline : évalue un batch de réponses pour l'entraînement
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Prompt système pour le juge de qualité
_JUDGE_SYSTEM_PROMPT = """Tu es un évaluateur de qualité pour un système de compression de prompts LLM.
Ton rôle est de comparer deux réponses d'IA :

- **Réponse A** : réponse de référence (sans compression)
- **Réponse B** : réponse avec compression du prompt

Évalue la **préservation de la qualité** de la réponse B par rapport à A.
Note sur une échelle de 0 à 100 les critères suivants, en tenant compte
du fait que la compression peut perdre des détails mineurs mais doit
préserver l'essentiel :

1. **Exactitude factuelle** : Les faits, chiffres, dates sont-ils préservés ?
2. **Complétude** : Tous les points clés de A sont-ils dans B ?
3. **Cohérence** : Le raisonnement est-il logique et bien structuré ?
4. **Fidélité** : B ne contredit-il pas A ?
5. **Style** : Le ton, le niveau de détail sont-ils similaires ?

Réponds UNIQUEMENT par un objet JSON valide :
{"score": <moyenne 0-100>, "details": {"exactitude": <0-100>, "completude": <0-100>, "coherence": <0-100>, "fidelite": <0-100>, "style": <0-100>, "justification": "<1 phrase>"}}

Ne mets RIEN d'autre que le JSON dans ta réponse."""


class QualityJudge:
    """Évaluateur qualité basé sur GPT-4o.

    Peut fonctionner avec ou sans clé API OpenAI.
    Sans clé, retourne un score par défaut (0.85).
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = None
        self._stats = {"evaluations": 0, "total_latency_ms": 0}

    def _get_client(self):
        if self._client is None and self._api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key, timeout=30)
            except Exception as e:
                logger.warning("OpenAI client not available: %s", e)
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    def evaluate(
        self,
        prompt: str,
        response_a: str,
        response_b: str,
        max_retries: int = 2,
    ) -> Dict:
        """Compare response_b (compressée) à response_a (référence).

        Retourne : {"score": float, "details": dict, "error": str|None}
        """
        client = self._get_client()
        if not client:
            return {
                "score": 0.85,
                "details": {"justification": "Judge non disponible, score par défaut"},
                "error": "no_api_key",
            }

        user_msg = (
            f"Prompt original :\n{prompt[:2000]}\n\n"
            f"Réponse A (référence) :\n{response_a[:4000]}\n\n"
            f"Réponse B (compressée) :\n{response_b[:4000]}\n\n"
            "Compare B à A et donne ton score."
        )

        for attempt in range(max_retries):
            try:
                t0 = time.time()
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.0,
                    max_tokens=300,
                )
                latency = (time.time() - t0) * 1000
                self._stats["evaluations"] += 1
                self._stats["total_latency_ms"] += latency

                content = resp.choices[0].message.content.strip()
                # Extraire le JSON de la réponse
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                result = json.loads(content)
                score = max(0.0, min(1.0, result.get("score", 85) / 100.0))
                details = result.get("details", {})
                return {"score": score, "details": details, "error": None}

            except Exception as e:
                logger.warning("Quality judge attempt %d failed: %s", attempt + 1, e)
                if attempt == max_retries - 1:
                    return {
                        "score": 0.85,
                        "details": {"justification": f"Échec juge: {e}"},
                        "error": str(e),
                    }
                time.sleep(1)

        return {"score": 0.85, "details": {"justification": "Max retries"}, "error": "max_retries"}

    def evaluate_batch(
        self,
        pairs: List[Tuple[str, str, str]],
        concurrency: int = 3,
    ) -> List[Dict]:
        """Évalue un batch de paires (prompt, response_a, response_b).

        En séquence (pas de vraie concurrence sans async).
        """
        results = []
        for prompt, resp_a, resp_b in pairs:
            r = self.evaluate(prompt, resp_a, resp_b)
            results.append(r)
        return results

    def get_stats(self) -> Dict:
        s = self._stats
        return {
            "evaluations": s["evaluations"],
            "avg_latency_ms": round(s["total_latency_ms"] / max(s["evaluations"], 1)),
        }


# Singleton
_judge_instance: Optional[QualityJudge] = None


def get_judge(api_key: Optional[str] = None) -> QualityJudge:
    global _judge_instance
    if _judge_instance is None:
        _judge_instance = QualityJudge(api_key=api_key)
    return _judge_instance
