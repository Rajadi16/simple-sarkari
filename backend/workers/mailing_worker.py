"""
Mailing worker — background tasks for dispatching emails.
"""

from __future__ import annotations

import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.mailing_service import send_urgent_circular_email
from models.circular import CanonicalCircular

logger = logging.getLogger(__name__)


async def process_pending_urgent_emails(db: AsyncIOMotorDatabase) -> int:
    """
    Background task: poll the database for newly published, high urgency circulars
    that have not yet been dispatched, and send emails for them.
    Returns the number of emails sent.
    """
    query = {
        "simplification.urgency_level": "high",
        "processing.published": True,
        "processing.email_dispatched": False,
    }
    
    # We could limit the query if we have a lot of backlogged items
    cursor = db.circulars.find(query).limit(50)
    circulars_data = await cursor.to_list(length=50)
    
    if not circulars_data:
        return 0
        
    # Fetch active subscribers
    subscribers_cursor = db.subscribers.find({"is_active": True}, {"email": 1})
    subscribers_list = await subscribers_cursor.to_list(length=10000)
    recipients = [sub['email'] for sub in subscribers_list if 'email' in sub]
    
    if not recipients:
        logger.info("No active subscribers found. Skipping email dispatch.")
        return 0
        
    emails_sent = 0
    for doc in circulars_data:
        try:
            circular = CanonicalCircular(**doc)
            success = send_urgent_circular_email(circular, recipients)
            
            if success:
                await db.circulars.update_one(
                    {"id": circular.id},
                    {"$set": {"processing.email_dispatched": True}}
                )
                emails_sent += 1
                logger.info(f"Successfully dispatched urgent email for circular {circular.id}")
            else:
                logger.warning(f"Failed to dispatch email for circular {circular.id}")
        except Exception as e:
            logger.error(f"Error processing email dispatch for circular {doc.get('id')}: {e}")
            
    return emails_sent
