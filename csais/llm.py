"""Klien LLM lokal lewat API yang kompatibel dengan OpenAI (LM Studio, Ollama, vLLM).

LM Studio menyediakan server di ``http://localhost:1234/v1`` setelah "Start
Server" di tab Developer. Semua pengaturan lewat variabel lingkungan (.env):

  LLM_BASE_URL      misalnya http://localhost:1234/v1 (kosong = LLM tidak dipakai)
  LLM_MODEL         nama model seperti tampil di LM Studio, misalnya qwen3.5-9b
  LLM_API_KEY       opsional; LM Studio tidak memeriksanya
  LLM_TIMEOUT       detik per permintaan (default 120)
  LLM_NO_THINK      1 = tambahkan /no_think (model Qwen) agar tidak menulis penalaran panjang
  LLM_JSON_SCHEMA   0 = jangan kirim response_format json_schema (untuk server lama)

Model Qwen dapat menulis blok ``<think>...</think>`` sebelum jawabannya, atau
LM Studio memisahkannya ke ``reasoning_content``; keduanya dibuang sebelum
JSON dibaca. Dengan Qwen3.5 di LM Studio, jawaban JSON bisa masuk ke
``reasoning_content`` sementara ``content`` kosong; kolom itu dipakai bila
``content`` kosong.
"""

import json
import os
import re

import requests

DEFAULT_TIMEOUT = 120
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LLMError(RuntimeError):
    pass


def settings():
    return {
        "base_url": (os.environ.get("LLM_BASE_URL") or "").rstrip("/"),
        "model": os.environ.get("LLM_MODEL") or "",
        "api_key": os.environ.get("LLM_API_KEY") or "lm-studio",
        "timeout": float(os.environ.get("LLM_TIMEOUT") or DEFAULT_TIMEOUT),
        "no_think": (os.environ.get("LLM_NO_THINK") or "1") == "1",
        "json_schema": (os.environ.get("LLM_JSON_SCHEMA") or "1") == "1",
    }


def configured():
    config = settings()
    return bool(config["base_url"] and config["model"])


def parse_json_text(text):
    """Ambil objek JSON dari jawaban model (buang <think>, pagar ```, teks di sekitarnya)."""
    text = _THINK.sub("", text or "").strip()
    text = _FENCE.sub("", text).strip()
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except ValueError:
                pass
    raise LLMError(f"jawaban model bukan JSON: {text[:200]!r}")


class LLMClient:
    """Permintaan chat completions dengan keluaran JSON."""

    def __init__(self, session=None, **overrides):
        self.config = {**settings(), **overrides}
        self.session = session or requests.Session()
        if not self.config["base_url"] or not self.config["model"]:
            raise LLMError("LLM_BASE_URL dan LLM_MODEL belum diisi")

    def _post(self, path, payload):
        response = self.session.post(
            f"{self.config['base_url']}{path}",
            json=payload,
            headers={"Authorization": f"Bearer {self.config['api_key']}"},
            timeout=self.config["timeout"],
        )
        return response

    def models(self):
        """Daftar id model yang dimuat server."""
        response = self.session.get(
            f"{self.config['base_url']}/models",
            headers={"Authorization": f"Bearer {self.config['api_key']}"},
            timeout=15,
        )
        response.raise_for_status()
        return [item.get("id") for item in response.json().get("data", [])]

    def chat_json(self, system, user, schema, name="extraction", temperature=0.0, max_tokens=800):
        """Kirim satu percakapan dan kembalikan (objek JSON, info pemakaian)."""
        if self.config["no_think"]:
            user = f"{user}\n/no_think"
        payload = {
            "model": self.config["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.config["json_schema"]:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
        response = self._post("/chat/completions", payload)
        if response.status_code == 400 and "response_format" in payload:
            # server tanpa dukungan json_schema: ulangi tanpa, JSON dibaca dari teks
            payload = {key: value for key, value in payload.items() if key != "response_format"}
            response = self._post("/chat/completions", payload)
        if response.status_code >= 400:
            raise LLMError(f"server LLM {response.status_code}: {response.text[:200]}")
        body = response.json()
        try:
            message = body["choices"][0]["message"]
        except (KeyError, IndexError) as error:
            raise LLMError(f"jawaban server tidak dikenal: {body}") from error
        content = message.get("content") or ""
        if not content.strip():
            # LM Studio + Qwen3.5: dengan response_format, jawaban JSON kadang
            # masuk ke kolom penalaran dan content kosong
            content = message.get("reasoning_content") or message.get("reasoning") or ""
        return parse_json_text(content), body.get("usage") or {}
