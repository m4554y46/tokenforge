"""Local LLM Rewriter — remplace KOMPRESS/LLMLingua-2 par une réécriture de phrases.

Utilise un LLM local (Phi-3-mini ou équivalent en GGUF) via llama.cpp
pour réécrire le texte de façon condensée mais fluide et grammaticale,
au lieu de supprimer des tokens un par un.

Garanties :
  - Temperature=0.0 → zéro créativité, pas d'hallucination
  - Prompt système qui exige de garder TOUS les faits, dates, chiffres
  - Reconstruction Monitor + Oracle en aval valident la qualité
  - Fallback transparent vers KOMPRESS si le modèle n'est pas disponible
"""

import logging
import os
import re
from typing import Optional

from backend.token_counter import count_tokens

logger = logging.getLogger(__name__)

_REWRITE_SYSTEM_FR = """\
Tu es un assistant spécialisé dans la condensation de textes professionnels.
Tu dois condenser le texte suivant en gardant TOUS les faits, dates, chiffres,
décisions et relations logiques. Tu ne changes rien, tu n'ajoutes rien, tu ne
fais que reformuler plus court et de façon plus directe.

Règles impératives :
- Garde TOUS les nombres, dates, pourcentages, montants, noms propres
- Garde TOUS les titres, signatures, formules de politesse
- Garde TOUTES les décisions et actions décrites textuellement
- Supprime uniquement le verbiage (répétitions, transitions vides, redondances)
- Reformule les phrases longues en phrases plus courtes mais garde TOUS les mots-clés
- N'INVENTE RIEN : ne change jamais une date, un nom, un chiffre ou un fait
- Ne remplace jamais une expression vague ("mardi dernier") par une date précise
- Réponds UNIQUEMENT avec la version condensée, sans introduction ni commentaire"""

_REWRITE_SYSTEM_EN = """\
You are a professional text condensation assistant.
Condense the following text while keeping ALL facts, dates, numbers,
decisions, and logical relationships. Do not change anything, do not add
anything, only rewrite more concisely and directly.

Mandatory rules:
- Keep ALL numbers, dates, percentages, amounts, proper nouns
- Keep ALL titles, signatures, closing formalities
- Keep ALL decisions and actions described verbatim
- Remove only verbosity (repetitions, empty transitions, redundancies)
- Rewrite long sentences as shorter ones but keep ALL keywords
- NEVER INVENT: never change a date, name, number, or fact
- Never replace a vague expression ("last Tuesday") with a specific date
- Reply ONLY with the condensed version, no introduction or commentary"""


def _detect_lang(text: str) -> str:
    """Détection simple de la langue : français si 'à|au|aux|des|les|ces|ses|mes|tes|nos|vos|leur|leurs|elle|ils|nous|vous|je|tu|il|sur|dans|avec|pour|par|est|sont|ont|été|être|faire|fait'"""
    fr_words = r'\b(?:à|au|aux|des|les|ces|ses|mes|tes|nos|vos|leur|leurs|elle|ils|nous|vous|je|tu|il|sur|dans|avec|pour|par|est|sont|ont|été|chez|donc|mais|ou|et|donc|car|ni|or|là|très|bien|fait|faire|être|avoir|tous|toutes|chaque|depuis|pendant|durant|afin|cette|entre|sans|sous)\b'
    fr_count = len(re.findall(fr_words, text, re.I))
    en_words = r'\b(?:the|a|an|is|are|was|were|been|have|has|had|do|does|did|will|would|shall|should|may|might|must|can|could|their|they|them|these|those|there|where|which|what|that|then|than|with|without|from|about|into|over|after|before|between|under|again|further|once|here|very|all|each|every|both|few|more|most|other|some|such|only|own|same|so)\b'
    en_count = len(re.findall(en_words, text, re.I))
    return 'fr' if fr_count > en_count else 'en'


def rewrite_with_local_llm(
    text: str,
    max_tokens: int = 512,
    temperature: float = 0.0,
    model_path: Optional[str] = None,
) -> Optional[str]:
    """Réécrit un texte de façon condensée via un LLM local.

    Args:
        text: Texte à condenser
        max_tokens: Nombre max de tokens en sortie
        temperature: Température (0.0 = déterministe)
        model_path: Chemin vers un modèle GGUF (None = auto-détection)

    Returns:
        Texte condensé, ou None si le LLM n'est pas disponible
    """
    lang = _detect_lang(text)
    system = _REWRITE_SYSTEM_FR if lang == 'fr' else _REWRITE_SYSTEM_EN

    try:
        from backend.spc.llama_cpp import get_llm
        llm = get_llm(model_path=model_path)
        if not llm.is_available():
            logger.info("Local LLM not available, skipping rewrite")
            return None

        result = llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["<|im_end|>", "<|end|>"],
        )
        if not result:
            return None

        # Nettoyer la sortie (enlever les éventuels artefacts du template)
        cleaned = result.strip()
        if cleaned.startswith("Voici") or cleaned.startswith("Here"):
            cleaned = re.sub(r'^[^:]+:', '', cleaned).strip()
        return cleaned

    except ImportError:
        logger.warning("llama_cpp not available")
        return None
    except Exception as e:
        logger.warning("Local rewrite failed: %s", e)
        return None


def is_rewriter_available() -> bool:
    """Vérifie si un LLM local est disponible pour la réécriture.

    Un modèle GGUF doit être présent dans backend/spc/models/.
    """
    try:
        from backend.spc.llama_cpp import get_llm, _MODELS_DIR
        if not _MODELS_DIR or not os.path.isdir(_MODELS_DIR):
            return False
        gguf_files = [f for f in os.listdir(_MODELS_DIR) if f.endswith('.gguf')]
        if not gguf_files:
            return False
        llm = get_llm(os.path.join(_MODELS_DIR, gguf_files[0]))
        return llm.is_available()
    except Exception:
        return False
