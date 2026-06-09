"""Explainability — pourquoi, gain, risque de chaque optimisation."""

from typing import Any, Dict, List, Optional


class PromptExplainability:
    """Explique chaque décision d'optimisation TokenForge."""

    REASONS = {
        "compression": "Réduction sémantique via pipeline SPC — suppression du bruit sans perte critique",
        "cache_hit": "Réponse servie depuis le cache — zéro appel provider",
        "memory_injection": "Contexte mémoire injecté — évite de répéter les préférences utilisateur",
        "policy_bypass": "Politique de gouvernance — compression forcée ou contournée",
        "fallback": "Quality gate activé — texte original préservé pour garantir la qualité",
    }

    def explain_optimization(
        self, original_tokens: int, optimized_tokens: int,
        profile: str, fallback: bool = False,
        techniques: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        savings = round((1 - optimized_tokens / max(original_tokens, 1)) * 100, 1)
        techniques = techniques or []
        reasons = []
        if fallback:
            reasons.append({
                "type": "fallback", "why": self.REASONS["fallback"],
                "gain_summary": "Qualité préservée à 100%", "gain_usd": 0,
                "risk": "none",
            })
        else:
            reasons.append({
                "type": "compression",
                "why": self.REASONS["compression"],
                "gain_summary": f"~{savings}% tokens économisés",
                "gain_usd": 0,
                "risk": "low" if savings < 50 else "medium" if savings < 65 else "high",
                "profile": profile,
                "techniques": techniques,
            })
        return {
            "why": reasons,
            "gain": {
                "tokens_saved": original_tokens - optimized_tokens,
                "savings_percent": savings,
            },
            "risk": reasons[-1].get("risk", "unknown"),
            "recommendation": self._recommend(profile, savings, fallback),
        }

    def _recommend(self, profile: str, savings: float, fallback: bool) -> str:
        if fallback:
            return "Conserver l'original — la compression aurait dégradé la qualité"
        if savings > 60 and profile in ("aggressive", "max", "industrial"):
            return "Valider avec un échantillon avant déploiement production"
        if savings > 30:
            return "Déploiement recommandé — ROI significatif, risque maîtrisé"
        return "Gain marginal — envisager un profil plus agressif"
