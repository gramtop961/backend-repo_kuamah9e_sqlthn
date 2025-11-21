"""
Database Schemas for Chat Character App

Each Pydantic model corresponds to a MongoDB collection (lowercased class name).
Use these schemas for validating requests and shaping responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# Core user profile (lightweight for demo; extend with auth in real app)
class UserProfile(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    age: Optional[int] = Field(None, ge=0, le=150)
    trust_score: int = Field(0, ge=0, le=100, description="Earned through positive interactions")

class Character(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    personality: str = Field(..., min_length=4, max_length=500)
    appearance: Optional[str] = Field(None, max_length=500, description="Key visual traits: hair, eyes, style")
    location: Optional[str] = Field(None, max_length=120)
    creator_username: str = Field(...)
    nsfw_allowed: bool = Field(False, description="Creator preference; still gated by trust")

class Message(BaseModel):
    character_id: str = Field(..., description="Target character ObjectId as string")
    username: str = Field(..., description="Who sent the message")
    text: str = Field(..., min_length=1, max_length=2000)
    role: Literal["user", "character"] = Field("user")

class ImageRequest(BaseModel):
    character_id: str
    username: str
    prompt: str = Field(..., min_length=4, max_length=400)
    style: Optional[str] = Field(None, description="Optional art style hint")
    rating: Literal["SFW", "NSFW"] = Field("SFW")

# Response shapes
class CharacterOut(BaseModel):
    id: str
    name: str
    personality: str
    appearance: Optional[str]
    location: Optional[str]
    creator_username: str
    nsfw_allowed: bool
    created_at: datetime

class MessageOut(BaseModel):
    id: str
    character_id: str
    username: str
    text: str
    role: Literal["user", "character"]
    created_at: datetime

class ImageJobOut(BaseModel):
    id: str
    character_id: str
    username: str
    prompt: str
    rating: Literal["SFW", "NSFW"]
    status: Literal["queued", "completed", "blocked"]
    image_url: Optional[str] = None
    created_at: datetime
