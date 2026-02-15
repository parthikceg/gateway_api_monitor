"""AI-powered change analysis using OpenAI"""

from openai import OpenAI
from typing import Dict, Any, Optional, List
import asyncio
import json
import logging
import os
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AIAnalyzer:
    """Uses AI to analyze and summarize API changes"""

    def __init__(self):
        # Support both Replit (AI_INTEGRATIONS_*) and local (OPENAI_API_KEY) env vars
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL") or None

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        self.ai_enabled = bool(api_key)
        logger.info(f"AI Analyzer enabled: {self.ai_enabled}")

    def classify_severity(self, change: Dict[str, Any]) -> str:
        """Rule-based severity classification — no AI needed"""
        change_type = change.get("change_type", "")
        field_path = change.get("field_path", "")
        is_required = change.get("is_required", False)

        # High severity: breaking changes
        high_severity_types = {
            "property_removed",
            "type_changed",
            "field_now_required",
            "enum_values_removed",
        }
        if change_type in high_severity_types:
            return "high"

        # Required field changes are always at least medium
        if is_required and change_type in {"property_added", "description_changed"}:
            return "medium"

        # Medium severity: structural changes
        medium_severity_types = {
            "property_added",
            "field_no_longer_required",
            "enum_values_added",
        }
        if change_type in medium_severity_types:
            return "medium"

        # Low severity: non-breaking, informational
        low_severity_types = {
            "description_changed",
        }
        if change_type in low_severity_types:
            return "low"

        # Default
        return "info"

    def categorize_change(self, change: Dict[str, Any]) -> str:
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
            "description_changed": "documentation",
        }

        return categories.get(change_type, "other")

    # Max changes per AI call — keeps prompt/response small enough for reliable JSON parsing
    BATCH_CHUNK_SIZE = 15
    # Max concurrent AI API calls — prevents rate limiting from OpenAI
    MAX_CONCURRENT_AI_CALLS = 3
    # Max retries per chunk
    MAX_RETRIES = 2

    async def batch_summarize(self, changes: List[Dict[str, Any]]) -> List[Optional[str]]:
        """Generate AI summaries for changes, chunked into manageable batches.

        Returns a list of summaries in the same order as the input changes.
        If AI is not enabled or a chunk fails, uses rule-based fallback summaries for that chunk.
        """
        if not changes:
            return []

        # Generate fallback summaries first (always available)
        fallback_summaries = [self._generate_fallback_summary(c) for c in changes]

        if not self.ai_enabled:
            logger.info("AI not enabled, using rule-based summaries")
            return fallback_summaries

        # Semaphore limits concurrent API calls to avoid rate limiting
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_AI_CALLS)

        # Build all chunks
        tasks = []
        for i in range(0, len(changes), self.BATCH_CHUNK_SIZE):
            chunk = changes[i:i + self.BATCH_CHUNK_SIZE]
            chunk_fallbacks = fallback_summaries[i:i + self.BATCH_CHUNK_SIZE]
            tasks.append(self._summarize_chunk_async(chunk, chunk_fallbacks, semaphore))

        # Run AI calls in parallel (limited by semaphore)
        logger.info(f"Running {len(tasks)} AI chunks (max {self.MAX_CONCURRENT_AI_CALLS} concurrent)...")
        chunk_results = await asyncio.gather(*tasks)

        all_summaries = []
        for result in chunk_results:
            all_summaries.extend(result)

        logger.info(f"Batch AI summarization complete: {len(all_summaries)} summaries")
        return all_summaries

    async def _summarize_chunk_async(self, changes: List[Dict[str, Any]], fallbacks: List[str], semaphore: asyncio.Semaphore) -> List[str]:
        """Run sync OpenAI call in a thread, rate-limited by semaphore."""
        async with semaphore:
            return await asyncio.to_thread(self._summarize_chunk, changes, fallbacks)

    def _summarize_chunk(self, changes: List[Dict[str, Any]], fallbacks: List[str]) -> List[str]:
        """Summarize a single chunk of changes with one AI call, with retries."""
        import time

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                prompt = self._build_batch_prompt(changes)

                response = self.client.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert API analyst. "
                                "Provide concise, business-focused summaries of API changes. "
                                "Return a JSON array of summary strings, one per change, in the same order as provided. "
                                "Each summary should be 1-2 sentences max."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    max_completion_tokens=2000,
                )

                content = response.choices[0].message.content
                if not content or not content.strip():
                    logger.warning(f"AI returned empty content (attempt {attempt}/{self.MAX_RETRIES})")
                    if attempt < self.MAX_RETRIES:
                        time.sleep(2 * attempt)
                        continue
                    return fallbacks

                content = content.strip()

                # Handle markdown code blocks if present
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

                summaries = json.loads(content)

                if isinstance(summaries, list) and len(summaries) == len(changes):
                    logger.info(f"AI chunk summarized {len(changes)} changes")
                    return summaries
                else:
                    logger.warning(f"AI returned {len(summaries) if isinstance(summaries, list) else 'non-list'} summaries for {len(changes)} changes (attempt {attempt}/{self.MAX_RETRIES})")
                    if attempt < self.MAX_RETRIES:
                        time.sleep(2 * attempt)
                        continue
                    return fallbacks

            except Exception as e:
                logger.error(f"AI chunk summarization failed (attempt {attempt}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(2 * attempt)
                    continue
                return fallbacks

        return fallbacks

    def _build_batch_prompt(self, changes: List[Dict[str, Any]]) -> str:
        """Build a single prompt for all changes"""
        lines = ["Summarize each of the following Stripe API changes. Return a JSON array of short summaries (1-2 sentences each), in the same order.\n"]

        for i, change in enumerate(changes):
            change_type = change.get("change_type", "")
            field_path = change.get("field_path", "")
            endpoint = change.get("endpoint", "unknown")
            severity = change.get("severity", "info")
            old_value = change.get("old_value")
            new_value = change.get("new_value")

            old_str = json.dumps(old_value)[:200] if old_value else "None"
            new_str = json.dumps(new_value)[:200] if new_value else "None"

            lines.append(f"Change {i+1}: [{change_type}] {field_path} on {endpoint} (severity: {severity}). Old: {old_str}. New: {new_str}.")

        return "\n".join(lines)

    def _generate_fallback_summary(self, change: Dict[str, Any]) -> str:
        """Generate a readable summary without AI"""
        change_type = change.get("change_type", "unknown")
        field_path = change.get("field_path", "unknown field")
        endpoint = change.get("endpoint", "")

        endpoint_display = endpoint.replace('/v1/', '').replace('_', ' ').title() if endpoint else "API"

        templates = {
            "property_added": f"New field '{field_path}' added to {endpoint_display}. Review if relevant to your integration.",
            "property_removed": f"Field '{field_path}' removed from {endpoint_display}. Check if your integration depends on this field.",
            "type_changed": f"Data type changed for '{field_path}' in {endpoint_display}. Update your parsing logic accordingly.",
            "field_now_required": f"Field '{field_path}' is now required in {endpoint_display}. Ensure your requests include this field.",
            "field_no_longer_required": f"Field '{field_path}' is no longer required in {endpoint_display}. No action needed.",
            "enum_values_added": f"New enum values added for '{field_path}' in {endpoint_display}. Handle new possible values.",
            "enum_values_removed": f"Enum values removed from '{field_path}' in {endpoint_display}. Stop sending removed values.",
            "description_changed": f"Documentation updated for '{field_path}' in {endpoint_display}.",
        }

        return templates.get(change_type, f"Change detected in '{field_path}' on {endpoint_display}: {change_type}.")
