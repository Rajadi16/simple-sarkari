from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from datetime import datetime

from lib.db import get_db
from models.subscriber import Subscriber

router = APIRouter(tags=["subscribers"], prefix="/subscribers")

class SubscribeRequest(BaseModel):
    email: str

@router.post("")
async def subscribe(
    req: SubscribeRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Subscribe to email alerts for urgent circulars."""
    existing = await db.subscribers.find_one({"email": req.email})
    if existing:
        if not existing.get("is_active"):
            await db.subscribers.update_one(
                {"email": req.email},
                {"$set": {"is_active": True}}
            )
            return {"status": "resubscribed"}
        return {"status": "already_subscribed"}
        
    subscriber = Subscriber(email=req.email)
    await db.subscribers.insert_one(subscriber.model_dump(mode='json'))
    return {"status": "subscribed"}

@router.delete("/{email}")
async def unsubscribe(
    email: str,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Unsubscribe from email alerts."""
    result = await db.subscribers.update_one(
        {"email": email},
        {"$set": {"is_active": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"status": "unsubscribed"}
