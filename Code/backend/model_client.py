"""Client for the trained model server (OpenAI-compatible HTTP API)."""

import os
import time
import logging
import requests

logger = logging.getLogger(__name__)


class ModelClientError(Exception):
    pass


class ModelClient:
    def __init__(self, base_url=None, api_key=None, model=None, timeout=60,
                 max_tokens=512, temperature=0.2):
        self.base_url = (base_url or os.environ.get("MODEL_SERVER_URL", "")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("MODEL_SERVER_API_KEY", "")
        self.model = model or os.environ.get("MODEL_NAME", "")
        self.timeout = int(os.environ.get("MODEL_TIMEOUT_SEC", timeout))
        self.max_tokens = int(os.environ.get("MODEL_MAX_TOKENS", max_tokens))
        self.temperature = float(os.environ.get("MODEL_TEMPERATURE", temperature))

    @property
    def enabled(self):
        return bool(self.base_url)

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def health(self):
        if not self.enabled:
            return False, "MODEL_SERVER_URL not set"
        try:
            r = requests.get(f"{self.base_url}/v1/models", headers=self._headers(), timeout=10)
            if r.ok:
                return True, r.json()
            return False, r.text
        except Exception as e:
            return False, str(e)

    def generate(self, system_prompt, user_prompt):
        if not self.enabled:
            raise ModelClientError("MODEL_SERVER_URL not set")
        if not self.model:
            raise ModelClientError("MODEL_NAME not set")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        last_err = None
        for attempt in range(3):
            try:
                r = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                r.raise_for_status()
                data = r.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ModelClientError("No choices returned by model server")
                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    raise ModelClientError("Empty content from model server")
                return content
            except Exception as e:
                last_err = e
                logger.warning(f"Model server attempt {attempt + 1} failed: {e}")
                time.sleep(1 * (attempt + 1))
        raise ModelClientError(f"Model server failed after retries: {last_err}")
