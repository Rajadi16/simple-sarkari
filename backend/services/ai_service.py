"""
AI service — Amazon Bedrock integration for simplification and structured extraction.
"""

import json
import logging
import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from lib.aws import get_bedrock_client
from models.circular import CanonicalCircular, SimplificationBlock

logger = logging.getLogger(__name__)


# ─── Structured output schema ────────────────────────────────────────────────

class AIExtractionResult(BaseModel):
    """Validated output from Bedrock simplification."""
    urgency_level: str = Field(default="low")
    simplified_title: str
    summary: str
    simplified_text: str
    required_action: Optional[str] = None
    who_is_affected: Optional[str] = None
    important_dates: list[dict] = Field(default_factory=list)
    amounts: list[dict] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    deadlines: list[dict] = Field(default_factory=list)
    target_audience: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)


# ─── Fixed system prompt ─────────────────────────────────────────────────────

SIMPLIFICATION_SYSTEM_PROMPT = """You are a government document simplifier for Indian citizens. Your goal is to translate complex, bureaucratic legalese into plain English at an 8th-grade reading level.

Rules you MUST follow:
- Write at an 8th-grade reading level. Use short sentences and simple words.
- Strip out bureaucratic jargon entirely.
- Do not invent facts.
- Do not change dates or amounts.
- Do not reinterpret legal language.
- Mark uncertain information as uncertain.
- Include source excerpts to back every important fact.
- Return valid JSON only. Do not wrap in markdown blocks like ```json.

JSON Structure:
- urgency_level (string): Must be "high", "medium", or "low". Use "high" ONLY if the document contains an impending deadline, a severe penalty for inaction, or an immediate public safety warning. Use "medium" for general required actions without immediate deadlines. Use "low" for informational press releases or routine updates.
- simplified_title (string): A short, clear title a citizen would understand.
- summary (string): A 2-3 sentence overview of the document at an 8th-grade level.
- simplified_text (string): The full explanation, broken down simply without jargon.
- required_action (string, optional): What exactly a citizen needs to do (if anything).
- who_is_affected (string, optional): Who this directly applies to.
- important_dates (list of objects): Each object must have "description" (string) and "date" (YYYY-MM-DD or readable string).
- amounts (list of objects): Each object must have "description" (string) and "amount" (string with currency/value).
- eligibility (list of strings): Who is eligible for this scheme/order.
- keywords (list of strings): 3-5 tags for search (e.g. "scholarship", "agriculture").
- key_points (list of strings): Main takeaways.
- action_items (list of strings): Specific steps to take.
- deadlines (list of objects): Same format as important_dates, but strictly for deadlines.
- target_audience (list of strings): Categories of people impacted.
- warnings (list of strings): Critical warnings or caveats.
- source_excerpts (list of strings): Exact quotes from the original text proving your claims.

Return a JSON object with EXACTLY these fields. Use null or empty lists if a field is not applicable.
"""


async def simplify_document(original_text: str) -> AIExtractionResult:
    """
    Call Bedrock to simplify a government document.
    """
    settings = get_settings()
    client = get_bedrock_client()
    
    # We use converse API which is cleaner for Claude 3
    messages = [
        {
            "role": "user",
            "content": [{"text": f"Here is the official document:\n\n<document>\n{original_text}\n</document>\n\nPlease simplify it and return ONLY valid JSON."}]
        }
    ]
    
    system = [{"text": SIMPLIFICATION_SYSTEM_PROMPT}]
    
    try:
        response = await asyncio.to_thread(
            client.converse,
            modelId=settings.bedrock_model_id,
            messages=messages,
            system=system,
            inferenceConfig={
                "maxTokens": 4096,
                "temperature": 0.0,
            },
        )
        
        output_text = response['output']['message']['content'][0]['text']
        
        # Strip potential markdown formatting if model didn't listen
        if output_text.startswith("```json"):
            output_text = output_text[7:]
        if output_text.endswith("```"):
            output_text = output_text[:-3]
            
        output_dict = json.loads(output_text.strip())
        return AIExtractionResult.model_validate(output_dict)
        
    except Exception as e:
        logger.error(f"Failed to simplify document via Bedrock: {str(e)}")
        raise


async def process_simplification(db: AsyncIOMotorDatabase, circular_id: str) -> None:
    """
    Full simplification pipeline for a circular.
    """
    # 1. Load circular from DB
    doc = await db.circulars.find_one({"_id": circular_id} if not circular_id.startswith("circular_") else {"id": circular_id})
    if not doc:
        raise ValueError(f"Circular {circular_id} not found")
        
    circular = CanonicalCircular.model_validate(doc)
    
    # Get text to simplify
    text_to_simplify = circular.content.clean_text or circular.content.original_text
    if not text_to_simplify:
        raise ValueError(f"Circular {circular_id} has no extracted text")

    # 2. Call simplify_document
    result = await simplify_document(text_to_simplify)
    
    # 3. Create SimplificationBlock
    simplification = SimplificationBlock(
        urgency_level=result.urgency_level,
        simplified_title=result.simplified_title,
        summary=result.summary,
        simplified_text=result.simplified_text,
        required_action=result.required_action,
        who_is_affected=result.who_is_affected,
        important_dates=result.important_dates,
        amounts=result.amounts,
        eligibility=result.eligibility,
        keywords=result.keywords,
        key_points=result.key_points,
        action_items=result.action_items,
        deadlines=result.deadlines,
        target_audience=result.target_audience,
        warnings=result.warnings,
        source_excerpts=result.source_excerpts,
    )
    
    # 4. Update DB
    await db.circulars.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "simplification": simplification.model_dump(),
                "processing.status": "ai_draft_generated"
            }
        }
    )
