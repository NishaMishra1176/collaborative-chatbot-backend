"""
Chat API router for interacting with Google Gemini AI.
Requires valid JWT authentication.
"""

from fastapi import APIRouter, Depends, status

from app.models.user import User
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services.ai_service import ai_service
from app.services.auth_dependency import get_current_user

router = APIRouter()


@router.post(
    "",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send message to Google Gemini AI",
    responses={
        200: {"description": "Message generated successfully by Gemini AI."},
        401: {"description": "Missing, invalid, or expired JWT authentication token."},
        422: {"description": "Validation error (empty, whitespace, or exceeding 4000 characters)."},
        502: {"description": "Gemini AI API failure or empty response."},
        503: {"description": "GEMINI_API_KEY is not configured in .env."},
        504: {"description": "Gemini AI service timed out."},
    },
)
def chat_message(
    chat_input: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Protected chat endpoint:
    - Requires valid JWT Bearer token
    - Validates message prompt (1 to 4000 characters, non-empty)
    - Invokes Google Gemini AI service
    - Returns structured AI response and model metadata
    """
    result = ai_service.generate_chat_response(
        prompt=chat_input.message,
        user_id=current_user.id,
    )
    return result
