"""Stripe API crawler service"""
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class StripeCrawler:
    """Fetches Stripe API specifications from GitHub"""
    
    # Stripe OpenAPI spec URLs - Multi-tier
    SPEC_URLS = {
        "stable": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json",
        "preview": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.sdk.json",
        "beta": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.beta.sdk.json"
    }
    
    async def fetch_spec(self, spec_type: str = "stable") -> Dict[str, Any]:
        """
        Fetch OpenAPI specification from Stripe
        
        Args:
            spec_type: One of 'stable', 'preview', or 'beta'
        """
        url = self.SPEC_URLS.get(spec_type)
        if not url:
            raise ValueError(f"Invalid spec_type: {spec_type}")
        
        logger.info(f"Fetching {spec_type} spec from: {url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    
    async def get_payment_intents_snapshot(self, spec_type: str = "stable") -> Dict[str, Any]:
        """
        Extract Payment Intents endpoint schema from spec
        
        Args:
            spec_type: One of 'stable', 'preview', or 'beta'
        """
        spec = await self.fetch_spec(spec_type)
        
        # Extract POST /v1/payment_intents endpoint
        payment_intents_path = spec.get("paths", {}).get("/v1/payment_intents", {})
        post_endpoint = payment_intents_path.get("post", {})
        
        if not post_endpoint:
            raise ValueError("Payment Intents POST endpoint not found in spec")
        
        # Extract request schema
        request_body = post_endpoint.get("requestBody", {})
        content = request_body.get("content", {}).get("application/x-www-form-urlencoded", {})
        schema = content.get("schema", {})
        
        # Return structured snapshot
        return {
            "endpoint": "/v1/payment_intents",
            "methods": {"post": post_endpoint.get("summary", "")},
            "schema": schema,
            "properties": schema.get("properties", {}),
            "required": schema.get("required", [])
        }