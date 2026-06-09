"""Client Python pour TokenForge Intelligence Platform."""

from typing import Any, Dict, Optional

import httpx


class TokenForgeClient:
    """SDK Python — proxy LLM + analytics enterprise."""

    def __init__(
        self, base_url: str = "http://127.0.0.1:8765",
        api_key: str = "", tenant_id: str = "default", user_id: str = "sdk",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.user_id = user_id
        self._client = httpx.Client(timeout=120)

    def _headers(self) -> Dict[str, str]:
        h = {"X-Tenant-ID": self.tenant_id, "X-User-ID": self.user_id}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def health(self) -> Dict:
        return self._client.get(f"{self.base_url}/api/v2/health").json()

    def dashboard(self) -> Dict:
        return self._client.get(f"{self.base_url}/api/v2/dashboard", headers=self._headers()).json()

    def get_user_profile(self) -> Dict:
        return self._client.get(f"{self.base_url}/api/v2/memory/user/profile", headers=self._headers()).json()

    def update_user_profile(self, updates: Dict[str, Any]) -> Dict:
        return self._client.put(
            f"{self.base_url}/api/v2/memory/user/profile",
            json={"updates": updates}, headers=self._headers(),
        ).json()

    def finops_roi(self) -> Dict:
        return self._client.get(f"{self.base_url}/api/v2/finops/roi", headers=self._headers()).json()

    def route_request(self, prompt: str, model: str = "gpt-4o") -> Dict:
        return self._client.post(
            f"{self.base_url}/api/v2/gateway/route",
            json={"prompt": prompt, "model": model},
            headers=self._headers(),
        ).json()

    def chat_completions(self, messages: list, model: str = "gpt-4o", **kwargs) -> Dict:
        """Appel OpenAI-compatible via le proxy TokenForge."""
        return self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json={"model": model, "messages": messages, **kwargs},
            headers={"Authorization": f"Bearer {self.api_key or 'sk-tokenforge'}"},
        ).json()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
