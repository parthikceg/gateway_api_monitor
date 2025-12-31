"""AI-powered change analysis using OpenAI"""
from openai import OpenAI
from typing import Dict, Any, Optional
import json
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class AIAnalyzer:
    """Uses AI to analyze and summarize API changes"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    async def analyze_change(self, change: Dict[str, Any]) -> Optional[str]:
        """Generate AI summary for a single change"""
        try:
            prompt = self._build_prompt(change)
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert API analyst. Provide concise, business-focused summaries of API changes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return None
    
    def _build_prompt(self, change: Dict[str, Any]) -> str:
        """Build prompt for AI analysis"""
        change_type = change.get("change_type", "")
        field_path = change.get("field_path", "")
        old_value = change.get("old_value")
        new_value = change.get("new_value")
        severity = change.get("severity", "unknown")
        
        prompt = f"""Analyze this API change for Stripe Payment Intents:

Change Type: {change_type}
Field: {field_path}
Severity: {severity}
Old Value: {json.dumps(old_value, indent=2) if old_value else "None"}
New Value: {json.dumps(new_value, indent=2) if new_value else "None"}

Provide a concise summary (2-3 sentences) covering:
1. What changed and why it matters
2. Potential impact on developers
3. Recommended action (if any)
"""
        return prompt
    
    async def categorize_change(self, change: Dict[str, Any]) -> str:
        """Categorize the type of change"""
        change_type = change.get("change_type", "")
        
        categories = {
            "property_added": "enhancement",
            "property_removed": "breaking_change",
            "type_changed": "breaking_change",
            "field_now_required": "breaking_change",
            "field_no_longer_required": "enhancement",
            "enum_values_added": "enhancement",
            "enum_values_removed": "breaking_change",
            "description_changed": "documentation"
        }
        
        return categories.get(change_type, "other")