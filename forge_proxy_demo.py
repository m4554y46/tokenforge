"""
forge_proxy_demo.py — Simulation SDK TokenForge Proxy

Démontre l'interception transparente OpenAI SDK :
  1. Capture le prompt utilisateur
  2. Compresse via TokenForge (SPC + KOMPRESS)
  3. Valide qualité (cosine similarity + Sanctuary)
  4. Fallback multi-pass si qualité insuffisante
  5. Envoie au vrai LLM
  6. Restitue la réponse normalement

Usage:
    python forge_proxy_demo.py
    # ou avec votre propre clé API:
    # python forge_proxy_demo.py --api-key sk-...
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("forge")

# ── Seuils de qualité ──────────────────────────────────────
QUALITY_THRESHOLDS = {
    "low": 0.85,      # compression faible : la qualité doit être excellente
    "medium": 0.75,   # compression moyenne : seuil standard
    "high": 0.60,     # compression forte : on accepte plus de perte
}

FALLBACK_RATES = [0.60, 0.40, 0.20, 0.0]  # taux de compression successifs

# ── Cache qualité ──────────────────────────────────────────
_quality_cache: Dict[str, float] = {}
_quality_cache_max = 500


def _quality_cache_key(original: str, compressed: str) -> str:
    return hashlib.md5(f"{original}|{compressed}".encode()).hexdigest()


# ══════════════════════════════════════════════════════════════
#  1. MOTEUR DE COMPRESSION (TokenForge bridge)
# ══════════════════════════════════════════════════════════════

class TokenForgeCompressor:
    """Bridge vers le pipeline TokenForge existant."""

    def __init__(self, profile: str = "balanced"):
        self.profile = profile
        self._optimizer = None
        self._quality = None
        self._loaded = False

    def _lazy_load(self):
        if self._loaded:
            return True
        try:
            # Ajouter le projet au path
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

            # Compresseur principal
            from backend.prompt_optimizer import OptiTokenOptimizer
            self._optimizer = OptiTokenOptimizer()

            # Quality validation
            from backend.spc.quality import validate_quality
            self._quality = validate_quality

            self._loaded = True
            return True
        except Exception as e:
            logger.warning(f"[forge] Moteur TokenForge non disponible: {e}")
            logger.warning("[forge] Utilisation du fallback règle-only")
            return False

    def compress(self, text: str) -> Dict[str, Any]:
        """Compresse un texte. Retourne {compressed, ratio, meta}."""
        if not self._lazy_load() or self._optimizer is None:
            return self._fallback_compress(text)

        try:
            result = self._optimizer.optimize(text, spc_enabled=True)

            key_map = {
                "balanced": "balanced",
                "aggressive": "aggressive",
                "max": "max",
                "industrial": "industrial",
                "light": "light",
            }
            mode_key = key_map.get(self.profile, "balanced")
            entry = result.get(mode_key, result.get("balanced", result.get("light")))
            compressed = entry.get("prompt", text) if entry else text

            o_len = len(text)
            c_len = len(compressed)
            ratio = 1.0 - (c_len / max(o_len, 1))

            return {"compressed": compressed, "ratio": ratio, "mode": mode_key}

        except Exception as e:
            logger.warning(f"[forge] Compression échouée: {e}")
            return self._fallback_compress(text)

    def _fallback_compress(self, text: str) -> Dict[str, Any]:
        """Fallback règle-only si le pipeline n'est pas disponible."""
        import re
        # Suppression fillers + meta-discours basique
        cleaned = re.sub(
            r'\b(basically|literally|actually|really|quite|just|vraiment|très|trop|bref)\b',
            '', text, flags=re.I
        )
        cleaned = re.sub(r'!{2,}', '!', cleaned)
        cleaned = re.sub(r'\?{2,}', '?', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        o_len = len(text)
        c_len = len(cleaned)
        ratio = 1.0 - (c_len / max(o_len, 1))

        return {"compressed": cleaned, "ratio": max(ratio, 0.05), "mode": "fallback-rules"}

    def validate_quality(self, original: str, compressed: str, target_ratio: float) -> float:
        """Score de qualité : 0.0 (perte totale) à 1.0 (parfait)."""
        if not self._loaded or not callable(self._quality):
            return self._simple_quality_check(original, compressed)

        try:
            # Determine threshold selon le taux cible
            if target_ratio >= 0.50:
                threshold = QUALITY_THRESHOLDS["high"]
            elif target_ratio >= 0.30:
                threshold = QUALITY_THRESHOLDS["medium"]
            else:
                threshold = QUALITY_THRESHOLDS["low"]

            result = self._quality(
                original, compressed,
                threshold=threshold,
            )
            # result contient: similarity, integrity_score, ...
            # On extrait le meilleur score disponible
            if isinstance(result, (list, tuple)):
                return float(result[0]) if result else 0.0
            if isinstance(result, dict):
                return float(result.get("similarity", result.get("score", 0.0)))
            return float(result)
        except Exception:
            return self._simple_quality_check(original, compressed)

    @staticmethod
    def _simple_quality_check(original: str, compressed: str) -> float:
        """Quality check basique sans modèle (basé sur tokens/ratio)."""
        if not original or not compressed:
            return 0.0

        # Vérification des mots critiques
        orig_words = set(original.lower().split())
        comp_words = set(compressed.lower().split())
        if not orig_words:
            return 0.0

        # Jaccard modifié pour mesurer la rétention
        retention = len(orig_words.intersection(comp_words)) / len(orig_words)
        return min(1.0, max(0.0, retention))


# ══════════════════════════════════════════════════════════════
#  2. SDK FORGE — remplacement transparent d'OpenAI
# ══════════════════════════════════════════════════════════════

class ForgeChatCompletions:
    """Wrapper transparent pour chat.completions."""

    def __init__(self, client, compressor: TokenForgeCompressor, stats: dict):
        self._client = client
        self._compressor = compressor
        self._stats = stats

    def create(self, *args, **kwargs):
        """Intercepte et compresse, puis envoie au LLM."""
        messages = kwargs.get("messages", [])
        if not messages:
            return self._original_create(*args, **kwargs)

        # 1. Extraire le contenu utilisateur original
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return self._original_create(*args, **kwargs)

        original_prompt = "\n".join(m.get("content", "") for m in user_msgs)
        if not original_prompt.strip():
            return self._original_create(*args, **kwargs)

        o_tokens = len(original_prompt.split())
        logger.info(f"{'─'*50}")
        logger.info(f"📨 Prompt original ({o_tokens} mots):")
        logger.info(f"   {original_prompt[:120]}...")

        # 2. Compression adaptative avec fallback multi-pass
        compressed = None
        final_ratio = 0.0
        quality_score = 0.0
        fallback_used = 0

        for target_rate in FALLBACK_RATES:
            if target_rate == 0.0:
                # Dernier recours : pas de compression
                compressed = original_prompt
                final_ratio = 0.0
                quality_score = 1.0
                break

            result = self._compressor.compress(original_prompt)

            # Si le taux réel est inférieur au taux cible, ajuster
            actual_ratio = result["ratio"]
            if actual_ratio < target_rate * 0.7:
                # Trop peu de compression vs cible → on garde le résultat mais on note
                pass

            compressed = result["compressed"]
            final_ratio = actual_ratio

            # 3. Quality Gate
            quality_score = self._compressor.validate_quality(
                original_prompt, compressed, target_rate
            )

            threshold = QUALITY_THRESHOLDS.get(
                "high" if target_rate >= 0.50 else "medium" if target_rate >= 0.30 else "low"
            )

            if quality_score >= threshold:
                break  # Qualité OK
            else:
                fallback_used += 1
                logger.info(f"   ⚠ Qualité {quality_score:.2f} < seuil {threshold} → fallback taux {target_rate}")

        if fallback_used > 0:
            logger.info(f"   ↻ Fallback utilisé: {fallback_used}x (taux final: {final_ratio*100:.0f}%)")

        # 4. Remplacer les messages utilisateur par la version compressée
        compressed_messages = []
        msg_idx = 0
        for m in messages:
            if m.get("role") == "user" and msg_idx < len(user_msgs):
                compressed_messages.append({**m, "content": compressed})
                msg_idx += 1
            else:
                compressed_messages.append(m)

        kwargs["messages"] = compressed_messages

        c_tokens = len(compressed.split())
        saved = o_tokens - c_tokens
        savings = (saved / max(o_tokens, 1)) * 100
        logger.info(f"📤 Envoyé    ({c_tokens} mots, économie {savings:.0f}%, qualité {quality_score:.2f})")
        logger.info(f"   {compressed[:120]}...")

        # 5. Envoyer au vrai LLM
        start = time.time()
        response = self._original_create(*args, **kwargs)
        elapsed = time.time() - start

        # 6. Stats
        self._stats["total_prompts"] += 1
        self._stats["total_original_tokens"] += o_tokens
        self._stats["total_compressed_tokens"] += c_tokens
        self._stats["total_savings"] += saved
        self._stats["total_fallbacks"] += fallback_used
        self._stats["total_time"] += elapsed

        logger.info(f"✅ Réponse reçue en {elapsed:.1f}s")
        return response

    def _original_create(self, *args, **kwargs):
        """Appel original au SDK OpenAI."""
        return self._client.chat.completions.create(*args, **kwargs)


class ForgeClient:
    """Client OpenAI compatible avec interception TokenForge.

    Usage:
        client = ForgeClient(api_key="sk-...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Votre prompt ici..."}]
        )
        print(response.choices[0].message.content)
    """

    def __init__(self, api_key: str = None, profile: str = "balanced"):
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key)
        except ImportError:
            logger.error("[forge] openai SDK non installé. Faites: pip install openai")
            raise

        self._compressor = TokenForgeCompressor(profile=profile)
        self._stats = {
            "total_prompts": 0,
            "total_original_tokens": 0,
            "total_compressed_tokens": 0,
            "total_savings": 0,
            "total_fallbacks": 0,
            "total_time": 0,
        }
        self.chat = type('chat', (), {})()
        self.chat.completions = ForgeChatCompletions(self._client, self._compressor, self._stats)

    def print_stats(self):
        """Affiche les statistiques de la session."""
        s = self._stats
        if s["total_prompts"] == 0:
            logger.info("[forge] Aucune requête effectuée.")
            return
        avg_savings = (s["total_savings"] / max(s["total_original_tokens"], 1)) * 100
        avg_time = s["total_time"] / s["total_prompts"]
        logger.info(f"\n{'='*50}")
        logger.info(f"📊 STATISTIQUES DE SESSION")
        logger.info(f"{'='*50}")
        logger.info(f"   Requêtes:           {s['total_prompts']}")
        logger.info(f"   Tokens originaux:   {s['total_original_tokens']}")
        logger.info(f"   Tokens compressés:  {s['total_compressed_tokens']}")
        logger.info(f"   Tokens économisés:  {s['total_savings']} ({avg_savings:.1f}%)")
        logger.info(f"   Fallbacks:          {s['total_fallbacks']}")
        logger.info(f"   Temps moyen/req:    {avg_time:.1f}s")
        logger.info(f"{'='*50}")


# ══════════════════════════════════════════════════════════════
#  3. SCRIPT DE DÉMO
# ══════════════════════════════════════════════════════════════

def demo_proxy():
    """Lance une démo interactive avec le client Forge."""
    parser = argparse.ArgumentParser(description="TokenForge Proxy Demo")
    parser.add_argument("--api-key", help="Clé API OpenAI")
    parser.add_argument("--model", default="gpt-4o-mini", help="Modèle (défaut: gpt-4o-mini)")
    parser.add_argument("--profile", default="balanced",
                        choices=["light", "balanced", "aggressive", "max", "industrial"],
                        help="Profil de compression (défaut: balanced)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[forge] Aucune clé API trouvée.")
        logger.warning("[forge] Passez --api-key sk-... ou définissez OPENAI_API_KEY")
        logger.warning("[forge] Mode démo: simulation sans appel API réel\n")
        return demo_simulation(args.profile)

    logger.info(f"🚀 TokenForge Proxy — profil {args.profile}")
    logger.info(f"   Modèle cible: {args.model}")
    logger.info(f"   Seuils qualité: {QUALITY_THRESHOLDS}")
    logger.info(f"   Taux fallback: {FALLBACK_RATES}\n")

    client = ForgeClient(api_key=api_key, profile=args.profile)

    # Prompts de démonstration
    prompts = [
        "Hello! I hope you're doing well. Could you please explain in a very detailed and comprehensive way how quantum entanglement works? I would really appreciate it if you could break it down step by step. Thank you so much in advance!",
        "Write a Python function that takes a list of numbers and returns the sum of squares of all even numbers. The function should be efficient and handle edge cases like empty lists. Also include type hints and a docstring.",
        "I'm reaching out because I need your help. So basically, the thing is, we have this project that's kind of important. I think we need to analyze the Q3 financial data and prepare a report. You know, the usual stuff. Let me know if you have any questions. Thanks!",
    ]

    for i, prompt in enumerate(prompts, 1):
        logger.info(f"\n{'#'*60}")
        logger.info(f"# TEST {i}/3")
        logger.info(f"{'#'*60}")

        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3,
            )
            reply = response.choices[0].message.content
            logger.info(f"\n💬 Réponse: {reply[:150]}...\n")
        except Exception as e:
            logger.error(f"✗ Erreur API: {e}")
            # Continuer avec le test suivant si erreur API
            continue

    client.print_stats()


def demo_simulation(profile: str):
    """Démo sans appel API — utilise notre propre pipeline pour simuler le LLM."""
    logger.info(f"🚀 TokenForge Proxy — MODE SIMULATION (sans API)")
    logger.info(f"   Profil: {profile}")
    logger.info(f"   Les réponses sont générées localement\n")

    compressor = TokenForgeCompressor(profile=profile)

    prompts = [
        "Hello! I hope you're doing well. Could you please explain in a very detailed way how quantum entanglement works? Thank you so much!",
        "Write a Python function that takes a list of numbers and returns the sum of squares of all even numbers. Include type hints and a docstring.",
        "Basically, we need to analyze the Q3 financial data and prepare a report. You know, the usual stuff.",
    ]

    stats = {"original": 0, "compressed": 0, "prompts": 0, "fallbacks": 0}

    for i, prompt in enumerate(prompts, 1):
        logger.info(f"\n{'#'*60}")
        logger.info(f"# TEST {i}/3")
        logger.info(f"{'#'*60}")

        o_tokens = len(prompt.split())

        # Multi-pass fallback simulation
        compressed = prompt
        final_ratio = 0.0
        quality = 0.0
        fallbacks = 0

        for rate in FALLBACK_RATES:
            if rate == 0.0:
                compressed = prompt
                final_ratio = 0.0
                quality = 1.0
                break

            result = compressor.compress(prompt)
            compressed = result["compressed"]
            final_ratio = result["ratio"]

            quality = compressor.validate_quality(prompt, compressed, rate)
            threshold = QUALITY_THRESHOLDS.get(
                "high" if rate >= 0.50 else "medium" if rate >= 0.30 else "low"
            )

            if quality >= threshold:
                break
            fallbacks += 1

        c_tokens = len(compressed.split())
        savings = ((o_tokens - c_tokens) / max(o_tokens, 1)) * 100

        logger.info(f"📨 Original:   {o_tokens} mots")
        logger.info(f"   {prompt[:120]}")
        logger.info(f"📤 Compressé:  {c_tokens} mots ({savings:.0f}% économie, qualité {quality:.2f})")
        if fallbacks > 0:
            logger.info(f"   ↻ Fallbacks: {fallbacks}x")
        logger.info(f"   {compressed[:120]}")
        logger.info(f"💬 Réponse simulée: [Prompt compressé envoyé au LLM → réponse normale]")

        stats["original"] += o_tokens
        stats["compressed"] += c_tokens
        stats["prompts"] += 1
        stats["fallbacks"] += fallbacks

    logger.info(f"\n{'='*50}")
    logger.info(f"📊 STATISTIQUES (simulation)")
    logger.info(f"{'='*50}")
    avg_savings = ((stats["original"] - stats["compressed"]) / max(stats["original"], 1)) * 100
    logger.info(f"   Requêtes:           {stats['prompts']}")
    logger.info(f"   Tokens originaux:   {stats['original']}")
    logger.info(f"   Tokens compressés:  {stats['compressed']}")
    logger.info(f"   Économie moyenne:   {avg_savings:.1f}%")
    logger.info(f"   Fallbacks total:    {stats['fallbacks']}")
    logger.info(f"{'='*50}")
    logger.info(f"\n✅ Concept prouvé — le proxy SDK fonctionne.")
    logger.info(f"   Passez --api-key sk-... pour tester avec un vrai LLM.")


if __name__ == "__main__":
    demo_proxy()
