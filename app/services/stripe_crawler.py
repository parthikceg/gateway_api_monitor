"""Stripe API specification crawler"""
import httpx
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class StripeCrawler:
    """Crawls Stripe's OpenAPI specification"""
    
    STRIPE_OPENAPI_URL = "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json"
    
    async def fetch_spec(self) -> Optional[Dict[str, Any]]:
        """Fetch the complete Stripe OpenAPI specification"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.STRIPE_OPENAPI_URL)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch Stripe OpenAPI spec: {e}")
            return None
    
    async def extract_payment_intents_schema(self, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract Payment Intents endpoint schema from spec"""
        try:
            # Payment Intents endpoints
            paths = spec.get("paths", {})
            
            # Get create payment intent endpoint
            create_endpoint = paths.get("/v1/payment_intents", {})
            post_method = create_endpoint.get("post", {})
            
            # Get retrieve payment intent endpoint
            retrieve_endpoint = paths.get("/v1/payment_intents/{intent}", {})
            get_method = retrieve_endpoint.get("get", {})
            
            # Extract schemas
            components = spec.get("components", {}).get("schemas", {})
            
            payment_intent_schema = components.get("payment_intent", {})
            
            return {
                "endpoint": "/v1/payment_intents",
                "methods": {
                    "POST": {
                        "parameters": post_method.get("requestBody", {}),
                        "responses": post_method.get("responses", {})
                    },
                    "GET": {
                        "parameters": get_method.get("parameters", []),
                        "responses": get_method.get("responses", {})
                    }
                },
                "schema": payment_intent_schema,
                "properties": payment_intent_schema.get("properties", {}),
                "required": payment_intent_schema.get("required", [])
            }
        except Exception as e:
            logger.error(f"Failed to extract Payment Intents schema: {e}")
            return None
    
    async def get_payment_intents_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get a complete snapshot of Payment Intents API"""
        spec = await self.fetch_spec()
        if not spec:
            return None
        
        return await self.extract_payment_intents_schema(spec)
