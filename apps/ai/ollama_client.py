import json
import urllib.error
import urllib.request
from django.conf import settings

class OllamaClientError(Exception):
    pass


class OllamaClient:

    def __init__(
        self,
        base_url=None,
        model=None,
        timeout=None,
    ):
        self.base_url = (
            base_url
            or settings.OLLAMA_BASE_URL
        ).rstrip("/")

        self.model = (
            model
            or settings.OLLAMA_MODEL
        )

        self.timeout = (
            timeout
            if timeout is not None
            else settings.OLLAMA_TIMEOUT
        )

    def generate(
        self,
        prompt,
        system=None,
    ):

        url = (
            f"{self.base_url}/api/generate"
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.1,
            },
        }
        if system:
            payload["system"] = system

        data = json.dumps(
            payload
        ).encode(
            "utf-8"
        )

        request = urllib.request.Request(
            url=url,
            data=data,
            headers={
                "Content-Type":
                    "application/json",
                "Accept":
                    "application/json",
            },
            method="POST",
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:

                raw = response.read()

        except urllib.error.HTTPError as exc:

            detail = exc.read().decode(
                "utf-8",
                errors="replace",
            )

            raise OllamaClientError(
                f"Ollama HTTP error "
                f"{exc.code}: {detail}"
            ) from exc

        except urllib.error.URLError as exc:

            raise OllamaClientError(
                "Cannot connect to Ollama. "
                "Make sure Ollama is running."
            ) from exc

        except TimeoutError as exc:

            raise OllamaClientError(
                "Ollama request timed out."
            ) from exc

        try:

            result = json.loads(
                raw.decode("utf-8")
            )

        except json.JSONDecodeError as exc:

            raise OllamaClientError(
                "Ollama returned invalid JSON."
            ) from exc

        response_text = (
            result.get("response")
            or ""
        ).strip()

        if not response_text:

            raise OllamaClientError(
                "Ollama returned an empty response."
            )

        return {
            "response": response_text,
            "model": result.get(
                "model",
                self.model,
            ),
            "done": result.get(
                "done",
                False,
            ),
            "raw": result,
        }
    