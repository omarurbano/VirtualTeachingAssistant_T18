import os
import time
import requests
from typing import Optional

NIM_API_BASE = os.getenv("NIM_API_BASE", "https://integrate.api.nvidia.com/v1")
NIM_API_KEY = os.getenv("NIM_API_KEY", "")
NIM_MODEL = os.getenv("NIM_MODEL", "meta/llama-3.1-70b-instruct")
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


class NIMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or NIM_API_KEY
        self.api_base = (api_base or NIM_API_BASE).rstrip("/")
        self.model = model or NIM_MODEL
        if not self.api_key:
            raise ValueError("NIM_API_KEY is required. Set it in your .env or environment.")

    def complete(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 1024) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stop": ["\n\nHuman:", "\n\nUser:"],
        }
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except requests.RequestException as exc:
                last_err = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF * attempt)
        raise RuntimeError(f"NIM API error after {MAX_RETRIES} retries: {last_err}")

    def complete_json(self, prompt: str, system_prompt: str = "", temperature: float = 0.3, max_tokens: int = 2048) -> dict:
        response = self.complete(prompt, system_prompt, temperature, max_tokens)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}")
            if start != -1 and end != -1:
                return json.loads(response[start : end + 1])
            return {"raw": response}
