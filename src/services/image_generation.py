from __future__ import annotations

import mimetypes
import re
from datetime import UTC, datetime
from hashlib import md5
from pathlib import Path
from typing import Any


class NanoBananaClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        output_dir: Path,
    ):
        self.api_key = api_key.strip()
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._client = None

    @staticmethod
    def _slug(prompt: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", prompt.strip().lower()).strip("-")
        return slug[:32] or "image"

    @staticmethod
    def _digest(prompt: str) -> str:
        return md5(prompt.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]

    def _build_path(self, prompt: str, extension: str) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = f"{self._slug(prompt)}-{self._digest(prompt)}-{stamp}{extension}"
        return self.output_dir / name

    def _save_image(self, prompt: str, mime_type: str, image_bytes: bytes) -> Path:
        extension = mimetypes.guess_extension(mime_type or "") or ".png"
        image_path = self._build_path(prompt, extension)
        image_path.write_bytes(image_bytes)
        return image_path

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from google import genai
        except Exception as exc:  # pragma: no cover - import path
            raise RuntimeError("google-genai is not installed. Run pip install -r requirements.txt.") from exc
        self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _build_subject_parts(self, types_module: Any, subject_images: list[dict[str, Any]]) -> tuple[list[Any], list[str]]:
        parts: list[Any] = []
        warnings: list[str] = []

        for idx, spec in enumerate(subject_images[:6], start=1):
            if not isinstance(spec, dict):
                continue

            name = str(spec.get("name", f"subject_{idx}")).strip() or f"subject_{idx}"
            mime_type = str(spec.get("mime_type", "")).strip() or mimetypes.guess_type(name)[0] or "image/png"

            data: bytes | None = None
            raw_data = spec.get("data")
            if isinstance(raw_data, (bytes, bytearray)):
                data = bytes(raw_data)
            else:
                raw_path = str(spec.get("path", "")).strip()
                if raw_path:
                    path = Path(raw_path)
                    if not path.is_absolute():
                        path = Path.cwd() / path
                    if path.exists():
                        try:
                            data = path.read_bytes()
                        except Exception as exc:  # pragma: no cover - filesystem path
                            warnings.append(f"Failed reading subject image '{name}': {exc}")
                    else:
                        warnings.append(f"Subject image file not found: {path}")

            if not data:
                warnings.append(f"Skipped subject image '{name}': no bytes available.")
                continue

            try:
                if hasattr(types_module.Part, "from_bytes"):
                    parts.append(types_module.Part.from_bytes(data=data, mime_type=mime_type))
                    continue
            except Exception as exc:  # pragma: no cover - sdk path
                warnings.append(f"Failed attaching subject image '{name}': {exc}")
                continue

            warnings.append(f"SDK missing Part.from_bytes; subject '{name}' was not attached.")

        return parts, warnings

    def generate_image(
        self,
        prompt: str,
        style: str = "",
        size: str = "1024x1024",
        subject_images: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        subject_images = subject_images or []
        if not self.api_key:
            return {
                "provider": "nano_banana_mock",
                "status": "mock",
                "image_url": "",
                "image_path": "",
                "subject_images_received": len(subject_images),
                "note": "Set GEMINI_API_KEY (or NANO_BANANA_API_KEY) to generate real images.",
            }

        try:
            client = self._get_client()
        except Exception as exc:
            return {
                "provider": "nano_banana_gemini",
                "status": "error",
                "image_url": "",
                "image_path": "",
                "subject_images_received": len(subject_images),
                "error": str(exc),
            }

        try:
            from google.genai import types
        except Exception as exc:  # pragma: no cover - import path
            return {
                "provider": "nano_banana_gemini",
                "status": "error",
                "image_url": "",
                "image_path": "",
                "subject_images_received": len(subject_images),
                "error": f"Failed to import google.genai types: {exc}",
            }

        text_prompt = prompt.strip()
        if style.strip():
            text_prompt += f"\nStyle guidance: {style.strip()}"
        if size.strip():
            text_prompt += f"\nTarget size: {size.strip()}"
        if subject_images:
            text_prompt += "\nUse the provided reference subject images as the primary visual subjects."

        subject_parts, subject_warnings = self._build_subject_parts(types, subject_images)

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=text_prompt), *subject_parts],
            ),
        ]
        config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])

        collected_text: list[str] = []
        try:
            for chunk in client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            ):
                if getattr(chunk, "text", None):
                    collected_text.append(chunk.text)
                parts = getattr(chunk, "parts", None) or []
                for part in parts:
                    if getattr(part, "text", None):
                        collected_text.append(part.text)
                    inline_data = getattr(part, "inline_data", None)
                    data = getattr(inline_data, "data", None) if inline_data else None
                    if data:
                        mime_type = getattr(inline_data, "mime_type", "image/png")
                        image_path = self._save_image(prompt=text_prompt, mime_type=mime_type, image_bytes=data)
                        return {
                            "provider": "nano_banana_gemini",
                            "status": "ok",
                            "image_url": str(image_path.as_posix()),
                            "image_path": str(image_path),
                            "mime_type": mime_type,
                            "subject_images_received": len(subject_images),
                            "subject_images_used": len(subject_parts),
                            "subject_warnings": subject_warnings,
                            "text": " ".join(collected_text).strip(),
                        }
        except Exception as exc:  # pragma: no cover - network path
            return {
                "provider": "nano_banana_gemini",
                "status": "error",
                "image_url": "",
                "image_path": "",
                "subject_images_received": len(subject_images),
                "subject_images_used": len(subject_parts),
                "subject_warnings": subject_warnings,
                "error": str(exc),
            }

        return {
            "provider": "nano_banana_gemini",
            "status": "error",
            "image_url": "",
            "image_path": "",
            "subject_images_received": len(subject_images),
            "subject_images_used": len(subject_parts),
            "subject_warnings": subject_warnings,
            "error": "No image bytes returned by the model.",
            "text": " ".join(collected_text).strip(),
        }
