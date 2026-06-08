"""llama.cpp wrapper — subprocess + optional python bindings.

Supports two backends:
  1. llama-cpp-python (if installed)
  2. llama-cli subprocess (if in PATH)
"""

import hashlib
import logging
import os
import subprocess
import time
from collections import OrderedDict
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "phi-3-mini-4k-instruct-q4.gguf"
_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")


class LlamaCpp:
    """Wrapper around llama.cpp inference.

    Tries llama-cpp-python first, falls back to llama-cli subprocess.
    """

    def __init__(self, model_path: Optional[str] = None, n_ctx: int = 4096, n_threads: int = 4):
        self.model_path = model_path or self._find_model()
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self._backend = None
        self._llama = None
        self._cache = OrderedDict()
        self._cache_max = 500
        self._cache_ttl = 3600  # 1 hour

    def _find_model(self) -> Optional[str]:
        """Locate a .gguf model in models/ directory."""
        if _MODELS_DIR and os.path.isdir(_MODELS_DIR):
            for f in os.listdir(_MODELS_DIR):
                if f.endswith(".gguf"):
                    return os.path.join(_MODELS_DIR, f)
        return None

    def is_available(self) -> bool:
        if self._llama is not None:
            return True
        if self.model_path and os.path.isfile(self.model_path):
            return True
        return self._check_llama_cli()

    @staticmethod
    def _check_llama_cli() -> bool:
        try:
            subprocess.run(["llama-cli", "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        try:
            subprocess.run(["llama-cli.exe", "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _load_backend(self) -> bool:
        if self._llama is not None:
            return True
        if self.model_path and not os.path.isfile(self.model_path):
            logger.warning("Model not found: %s", self.model_path)
            return False
        try:
            from llama_cpp import Llama
            self._llama = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                verbose=False,
            )
            self._backend = "python"
            logger.info("Loaded llama-cpp-python backend")
            return True
        except ImportError:
            logger.info("llama-cpp-python not installed, using subprocess backend")
            self._backend = "cli"
            return True
        except Exception as e:
            logger.warning("Failed to load llama-cpp-python: %s", e)
            self._backend = "cli"
            return True

    def generate(
        self,
        prompt: str,
        max_tokens: int = 64,
        temperature: float = 0.1,
        stop: Optional[list] = None,
    ) -> Optional[str]:
        cache_key = hashlib.md5((prompt + str(max_tokens)).encode()).hexdigest()
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        if not self._load_backend():
            return None

        try:
            if self._backend == "python":
                result = self._generate_python(prompt, max_tokens, temperature, stop)
            else:
                result = self._generate_cli(prompt, max_tokens, temperature, stop)

            if result:
                self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning("LLM generation failed: %s", e)
            return None

    def chat(
        self,
        messages: list,
        max_tokens: int = 64,
        temperature: float = 0.1,
        stop: Optional[list] = None,
    ) -> Optional[str]:
        """Chat completion using model's built-in chat template."""
        if not self._load_backend() or self._backend != "python":
            return self.generate(messages[-1]["content"] if messages else "", max_tokens, temperature, stop)

        try:
            output = self._llama.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop or [],
            )
            return output["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning("Chat completion failed, falling back to raw generation: %s", e)
            return self._generate_python(
                messages[-1]["content"] if messages else "",
                max_tokens, temperature, stop,
            )

    def _generate_python(self, prompt: str, max_tokens: int, temperature: float, stop: Optional[list]) -> Optional[str]:
        output = self._llama(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or [],
            echo=False,
        )
        choices = output.get("choices", [])
        if choices:
            return choices[0].get("text", "").strip()
        return None

    def _generate_cli(self, prompt: str, max_tokens: int, temperature: float, stop: Optional[list]) -> Optional[str]:
        cmd = ["llama-cli"]
        if self.model_path:
            cmd.extend(["-m", self.model_path])
        cmd.extend([
            "--temp", str(temperature),
            "-n", str(max_tokens),
            "-p", prompt,
        ])
        if stop:
            cmd.extend(["--stop"] + stop)
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            logger.warning("llama-cli error (rc=%d): %s", result.returncode, result.stderr[:200])
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning("llama-cli failed: %s", e)
            return None

    def _get_from_cache(self, key: str) -> Optional[str]:
        if key in self._cache:
            val, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                self._cache.move_to_end(key)
                return val
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: str):
        while len(self._cache) >= self._cache_max:
            self._cache.popitem(last=False)
        self._cache[key] = (value, time.time())


def get_llm(model_path: Optional[str] = None) -> LlamaCpp:
    return LlamaCpp(model_path=model_path)
