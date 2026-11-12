"""
Chat API router for interacting with Google Gemini AI.
Requires valid JWT authentication.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.chat_message import ChatMessage
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
    db: Session = Depends(get_db),
):
    """
    Protected chat endpoint:
    - Requires valid JWT Bearer token
    - Validates message prompt (1 to 4000 characters, non-empty)
    - Invokes Google Gemini AI service
    - Saves conversation history in MySQL database
    - Returns structured AI response and model metadata
    """
    result = ai_service.generate_chat_response(
        prompt=chat_input.message,
        user_id=current_user.id,
    )

    # Persist chat message to database
    try:
        record = ChatMessage(
            user_id=current_user.id,
            message=chat_input.message,
            response=result["response"],
            model=result["model"],
            created_at=result["timestamp"],
        )
        db.add(record)
        db.commit()
    except Exception as exc:
        db.rollback()
        # Even if DB write fails, don't break the user's generated AI answer

    return result


@router.get(
    "/history",
    status_code=status.HTTP_200_OK,
    summary="Retrieve chat conversation history for authenticated user",
    responses={
        200: {"description": "Conversation history retrieved successfully."},
        401: {"description": "Missing, invalid, or expired JWT authentication token."},
    },
)
def get_chat_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all previous messages sent and received by the current user from MySQL,
    sorted in chronological order.
    """
    records = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "message": r.message,
            "response": r.response,
            "model": r.model,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.delete(
    "/history",
    status_code=status.HTTP_200_OK,
    summary="Clear chat history for authenticated user",
)
def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes all saved chat messages for the current user from MySQL.
    """
    db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).delete()
    db.commit()
    return {"status": "success", "message": "Chat history cleared successfully."}
