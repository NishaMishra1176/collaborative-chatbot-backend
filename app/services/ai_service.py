"""
Dedicated AI Service integrating Google Gemini via the official google-genai SDK.
Handles client initialization, message generation, and error handling.
"""

import logging
from datetime import datetime, timezone
from fastapi import HTTPException, status
from google import genai
from google.genai import errors, types

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiAIService:
    """
    Service responsible for interacting with Google Gemini AI models.
    Ensures safe handling of API keys, timeouts, and API exceptions.
    """

    def __init__(self):
        self._client: genai.Client | None = None
        self._cached_api_key: str | None = None

    def get_client(self) -> genai.Client:
        """
        Lazily creates or returns the cached google-genai Client instance.
        Raises HTTPException(503) if GEMINI_API_KEY is not configured.
        """
        api_key = settings.GEMINI_API_KEY.strip()
        if not api_key:
            logger.error("Gemini AI request rejected: GEMINI_API_KEY is not set.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Gemini AI service is not configured. Please set your GEMINI_API_KEY "
                    "in the .env file."
                ),
            )

        # Reinitialize client if API key changed in settings
        if self._client is None or self._cached_api_key != api_key:
            self._client = genai.Client(api_key=api_key)
            self._cached_api_key = api_key

        return self._client

    def generate_chat_response(self, prompt: str, user_id: int) -> dict:
        """
        Sends user message to Google Gemini and returns the structured response.
        Never logs prompt contents or credentials.

        Raises:
            HTTPException(503): If GEMINI_API_KEY is missing.
            HTTPException(502): If Gemini API fails or returns empty output.
            HTTPException(504): If the request times out.
        """
        client = self.get_client()
        model_name = settings.GEMINI_MODEL or "gemini-3.5-flash"

        # Log metadata only - never log sensitive user prompts or credentials
        logger.info(
            "Generating Gemini response with model '%s' for authenticated user %s",
            model_name,
            user_id,
        )

        config = types.GenerateContentConfig(
            system_instruction=(
                "You are a helpful, professional, and concise customer-care AI assistant. "
                "Provide direct, crisp, and easily readable answers (typically 2 to 4 bullet points or short paragraphs). "
                "Avoid writing overly long essays or filler content unless the user explicitly requests extensive detail."
            ),
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            max_output_tokens=600,
        )

        try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
            except errors.APIError as initial_exc:
                if getattr(initial_exc, "code", None) == 503 and model_name != "gemini-3.5-flash-lite":
                    logger.warning(
                        "Gemini model '%s' busy (503). Retrying with resilient fallback 'gemini-3.5-flash-lite'...",
                        model_name,
                    )
                    model_name = "gemini-3.5-flash-lite"
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )
                else:
                    raise initial_exc
        except errors.APIError as exc:
            err_code = getattr(exc, "code", None)
            err_status = getattr(exc, "status", None)
            err_msg = getattr(exc, "message", str(exc))

            # Safe diagnostic logging: code, status, and message (never user prompt or API key)
            logger.error(
                "Gemini API error occurred: code=%s, status=%s, message=%s",
                err_code if err_code is not None else "unknown",
                err_status if err_status is not None else "unknown",
                err_msg,
            )

            err_msg_lower = err_msg.lower()
            if "api_key_invalid" in err_msg_lower or "api key not valid" in err_msg_lower or err_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Gemini API key is invalid. Please verify your GEMINI_API_KEY in the .env file.",
                ) from exc

            if err_code == 404 or "not found" in err_msg_lower or "no longer available" in err_msg_lower:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        f"Gemini AI service encountered an error while processing your request: "
                        f"The configured model '{model_name}' was not found or is no longer available. "
                        f"Please update GEMINI_MODEL in your .env file."
                    ),
                ) from exc

            if err_code == 429 or "resource_exhausted" in str(err_status).lower() or "quota" in err_msg_lower:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "Gemini AI service encountered an error while processing your request: "
                        "API rate limit or quota exceeded. Please try again later."
                    ),
                ) from exc

            if err_code == 503 or "unavailable" in str(err_status).lower():
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "Gemini AI service encountered an error while processing your request: "
                        "The model is temporarily overloaded or experiencing high demand. Please try again shortly."
                    ),
                ) from exc

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini AI service encountered an error while processing your request: {err_msg}",
            ) from exc
        except TimeoutError as exc:
            logger.error("Gemini request timed out for user ID %s", user_id)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Gemini AI service timed out. Please try again later.",
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error communicating with Gemini AI service.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="An unexpected error occurred while communicating with the AI service.",
            ) from exc

        generated_text = getattr(response, "text", None)
        if not generated_text or not generated_text.strip():
            logger.warning("Gemini model '%s' returned an empty response for user %s", model_name, user_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The AI model returned an empty response. Please try rephrasing your message.",
            )

        return {
            "response": generated_text.strip(),
            "model": model_name,
            "timestamp": datetime.now(timezone.utc),
        }


# Singleton instance
ai_service = GeminiAIService()
