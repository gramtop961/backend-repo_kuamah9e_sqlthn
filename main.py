import os
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db
from schemas import UserProfile, Character, ImageRequest, CharacterOut, MessageOut

app = FastAPI(title="Character Chat + Image App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utils

def doc_to_str_id(doc: dict) -> dict:
    d = doc.copy()
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


# Health
@app.get("/")
def root():
    return {"message": "Backend running", "database": bool(db)}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available" if db is None else "✅ Connected",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": os.getenv("DATABASE_NAME") or None,
        "collections": []
    }
    try:
        if db is not None:
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"⚠️ Error: {str(e)[:80]}"
    return response


# Users
@app.post("/users", response_model=UserProfile)
def upsert_user(profile: UserProfile):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    existing = db["userprofile"].find_one({"username": profile.username})
    payload = profile.model_dump()
    payload["updated_at"] = datetime.now(timezone.utc)
    if existing:
        db["userprofile"].update_one({"_id": existing["_id"]}, {"$set": payload})
        doc = db["userprofile"].find_one({"_id": existing["_id"]})
    else:
        payload["created_at"] = datetime.now(timezone.utc)
        payload["_id"] = profile.username  # readable primary key
        db["userprofile"].insert_one(payload)
        doc = payload
    return UserProfile(**{k: doc.get(k) for k in ["username", "age", "trust_score"]})


@app.get("/users/{username}", response_model=UserProfile)
def get_user(username: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    doc = db["userprofile"].find_one({"username": username})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(**{k: doc.get(k) for k in ["username", "age", "trust_score"]})


# Characters
@app.post("/characters", response_model=CharacterOut)
def create_character(character: Character):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    data = character.model_dump()
    now = datetime.now(timezone.utc)
    data["created_at"] = now
    data["updated_at"] = now
    data["_id"] = str(uuid4())
    db["character"].insert_one(data)
    out = doc_to_str_id(data)
    return CharacterOut(**{
        "id": out["id"],
        "name": out["name"],
        "personality": out["personality"],
        "appearance": out.get("appearance"),
        "location": out.get("location"),
        "creator_username": out["creator_username"],
        "nsfw_allowed": out.get("nsfw_allowed", False),
        "created_at": out["created_at"],
    })


@app.get("/characters", response_model=List[CharacterOut])
def list_characters():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    docs = list(db["character"].find().sort("created_at", -1))
    items: List[CharacterOut] = []
    for doc in docs:
        d = doc_to_str_id(doc)
        items.append(CharacterOut(
            id=d["id"],
            name=d["name"],
            personality=d["personality"],
            appearance=d.get("appearance"),
            location=d.get("location"),
            creator_username=d["creator_username"],
            nsfw_allowed=d.get("nsfw_allowed", False),
            created_at=d["created_at"],
        ))
    return items


# Chat messages
class ChatIn(BaseModel):
    username: str
    text: str


def generate_character_reply(character: dict, user_text: str) -> str:
    persona = character.get("personality", "kind and helpful")
    name = character.get("name", "Your character")
    prompt_safe = user_text[:400]
    reply = (
        f"{name}: As a {persona} character, I hear you say: '{prompt_safe}'. "
        "Here's my friendly response: I'm excited to chat and co-create images. "
        "Share more about style, mood, and setting!"
    )
    return reply


@app.post("/chat/{character_id}/messages", response_model=List[MessageOut])
def post_message(character_id: str, payload: ChatIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    char = db["character"].find_one({"_id": character_id})
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    now = datetime.now(timezone.utc)
    # Store user message
    user_msg = {
        "_id": str(uuid4()),
        "character_id": character_id,
        "username": payload.username,
        "text": payload.text,
        "role": "user",
        "created_at": now,
        "updated_at": now,
    }
    db["message"].insert_one(user_msg)

    # Store character reply (simple safe generator)
    reply_text = generate_character_reply(char, payload.text)
    char_msg = {
        "_id": str(uuid4()),
        "character_id": character_id,
        "username": char.get("name", "character"),
        "text": reply_text,
        "role": "character",
        "created_at": now,
        "updated_at": now,
    }
    db["message"].insert_one(char_msg)

    msgs = list(db["message"].find({"character_id": character_id}).sort("created_at", 1))
    out: List[MessageOut] = []
    for m in msgs:
        d = doc_to_str_id(m)
        out.append(MessageOut(
            id=d["id"],
            character_id=d["character_id"],
            username=d["username"],
            text=d["text"],
            role=d["role"],
            created_at=d["created_at"],
        ))
    return out


@app.get("/chat/{character_id}/messages", response_model=List[MessageOut])
def get_messages(character_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    msgs = list(db["message"].find({"character_id": character_id}).sort("created_at", 1))
    out: List[MessageOut] = []
    for m in msgs:
        d = doc_to_str_id(m)
        out.append(MessageOut(
            id=d["id"],
            character_id=d["character_id"],
            username=d["username"],
            text=d["text"],
            role=d["role"],
            created_at=d["created_at"],
        ))
    return out


# Image generation (demo: SFW placeholder, NSFW gated and blocked in this demo)
class ImageGenResponse(BaseModel):
    id: str
    status: str
    message: str
    image_url: Optional[str] = None


@app.post("/images", response_model=ImageGenResponse)
def generate_image(req: ImageRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    # Fetch character and user
    char = db["character"].find_one({"_id": req.character_id})
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    user = db["userprofile"].find_one({"username": req.username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.rating == "NSFW":
        return ImageGenResponse(
            id=str(uuid4()),
            status="blocked",
            message=(
                "NSFW image generation is gated and disabled in this demo. "
                "Earn trust and ensure adult age in a production-ready system."
            ),
            image_url=None,
        )

    desc = f"{char.get('name')} | {char.get('personality')} | {char.get('appearance') or ''} | {char.get('location') or ''} | {req.prompt}"
    seed = abs(hash(desc)) % 1000
    placeholder_url = f"https://picsum.photos/seed/{seed}/768/512"

    return ImageGenResponse(
        id=str(uuid4()),
        status="completed",
        message="SFW image created (placeholder)",
        image_url=placeholder_url,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
