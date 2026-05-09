"""
AI generator service - Multiple provider support (Gemini, Groq, Ollama)
"""
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings


class GeminiGenerator:
    """Generate report sections using Google Gemini API"""

    def __init__(self):
        self.api_key = getattr(settings, 'GEMINI_API_KEY', '')
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    async def generate_section(self, prompt: str, max_tokens: int = 4096) -> str:
        if not self.api_key:
            return "[ERROR: GEMINI_API_KEY not configured]"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
                "topK": 40,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}?key={self.api_key}",
                    json=payload,
                )

                if response.status_code != 200:
                    return f"[ERROR: Gemini API returned {response.status_code}: {response.text[:200]}]"

                result = response.json()
                if "candidates" not in result or not result["candidates"]:
                    return "[ERROR: No response from Gemini API]"

                return result["candidates"][0]["content"]["parts"][0]["text"].strip()

        except httpx.TimeoutException:
            return "[ERROR: Gemini API request timed out]"
        except Exception as e:
            return f"[ERROR: {str(e)}]"


class GroqGenerator:
    """Generate report sections using Groq API (Free tier, very fast)"""

    def __init__(self):
        self.api_key = getattr(settings, 'GROQ_API_KEY', '')
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        # Models: llama-3.3-70b-versatile, mixtral-8x7b-32768, llama-3.1-8b-instant
        self.model = getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile')

    async def generate_section(self, prompt: str, max_tokens: int = 4096) -> str:
        if not self.api_key:
            return "[ERROR: GROQ_API_KEY not configured]"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a Nepali government forest officer. Write reports in Nepali language (Devanagari script). Technical terms can be in English."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                )

                if response.status_code != 200:
                    return f"[ERROR: Groq API returned {response.status_code}: {response.text[:200]}]"

                result = response.json()
                if not result.get("choices"):
                    return "[ERROR: No response from Groq API]"

                return result["choices"][0]["message"]["content"].strip()

        except httpx.TimeoutException:
            return "[ERROR: Groq API request timed out]"
        except Exception as e:
            return f"[ERROR: {str(e)}]"


class OllamaGenerator:
    """Generate report sections using local Ollama (completely free, no API key)"""

    def __init__(self):
        self.base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        # Models: llama3.1, qwen2.5, mistral, neural-chat
        self.model = getattr(settings, 'OLLAMA_MODEL', 'llama3.1')

    async def generate_section(self, prompt: str, max_tokens: int = 4096) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": max_tokens,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )

                if response.status_code != 200:
                    return f"[ERROR: Ollama returned {response.status_code}: {response.text[:200]}]"

                result = response.json()
                if not result.get("response"):
                    return "[ERROR: No response from Ollama]"

                return result["response"].strip()

        except httpx.TimeoutException:
            return "[ERROR: Ollama request timed out. Make sure Ollama is running on localhost:11434]"
        except httpx.ConnectError:
            return "[ERROR: Cannot connect to Ollama. Install Ollama from https://ollama.com and run: ollama pull llama3.1]"
        except Exception as e:
            return f"[ERROR: {str(e)}]"


class FallbackGenerator:
    """Try multiple providers in order until one works"""

    def __init__(self):
        self.providers = []

        # Priority order: Groq (fast free) -> Gemini -> Ollama (local)
        if getattr(settings, 'GROQ_API_KEY', ''):
            self.providers.append(("Groq", GroqGenerator()))
        if getattr(settings, 'GEMINI_API_KEY', ''):
            self.providers.append(("Gemini", GeminiGenerator()))
        self.providers.append(("Ollama", OllamaGenerator()))

        if not self.providers:
            self.providers = [("Ollama", OllamaGenerator())]

    async def generate_section(self, prompt: str, max_tokens: int = 4096) -> str:
        errors = []
        for name, generator in self.providers:
            try:
                result = await generator.generate_section(prompt, max_tokens)
                if not result.startswith("[ERROR:"):
                    return result
                errors.append(f"{name}: {result}")
            except Exception as e:
                errors.append(f"{name}: {str(e)}")

        # All providers failed
        error_msg = "\n".join(errors)
        return f"[ERROR: All AI providers failed.\n\n{error_msg}\n\nPlease configure at least one:\n- GROQ_API_KEY (free: https://console.groq.com)\n- GEMINI_API_KEY (free: https://aistudio.google.com)\n- Install Ollama: https://ollama.com]"


# Singleton instance
_generator = None


def get_generator():
    global _generator
    if _generator is None:
        _generator = FallbackGenerator()
    return _generator
