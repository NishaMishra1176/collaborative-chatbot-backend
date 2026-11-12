"""
SQLAlchemy ChatMessage model definition.
Persists user prompts, AI responses, model metadata, and timestamps.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    """Returns current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


class ChatMessage(Base):
    """
    Database model storing chat conversations between users and Gemini AI.
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationship back to User
    user = relationship("User", backref="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, user_id={self.user_id}, model='{self.model}')>"
