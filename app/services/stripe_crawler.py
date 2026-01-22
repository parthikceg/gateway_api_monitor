"""Stripe API crawler service"""
import httpx
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class StripeCrawler:
    """Fetches Stripe API specifications from GitHub"""

    # Stripe OpenAPI spec URLs - Multi-tier
    SPEC_URLS = {
        "stable": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json",
        "preview": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.sdk.json",
        "beta": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.beta.sdk.json"
    }

    # Endpoints to monitor - organized by priority
    # Priority 1: Core Payment Processing (Integration as a Partner)
    MONITORED_ENDPOINTS = [
        "/v1/payment_intents",
        "/v1/payment_methods",
        "/v1/charges",
        "/v1/refunds",
        "/v1/customers",
        "/v1/checkout/sessions",
        "/v1/setup_intents",
        "/v1/payment_links",
    ]

    # Priority 2: Billing APIs (can be enabled later)
    # BILLING_ENDPOINTS = [
    #     "/v1/subscriptions",
    #     "/v1/invoices",
    #     "/v1/subscription_items",
    #     "/v1/prices",
    #     "/v1/products",
    # ]
    
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
        Extract Payment Intents endpoint schema from spec (legacy method for backwards compatibility)

        Args:
            spec_type: One of 'stable', 'preview', or 'beta'
        """
        return await self.get_endpoint_snapshot("/v1/payment_intents", spec_type)

    async def get_endpoint_snapshot(self, endpoint_path: str, spec_type: str = "stable") -> Dict[str, Any]:
        """
        Extract endpoint schema from spec for any given endpoint

        Args:
            endpoint_path: The API endpoint path (e.g., "/v1/payment_intents")
            spec_type: One of 'stable', 'preview', or 'beta'
        """
        spec = await self.fetch_spec(spec_type)

        # Extract endpoint
        endpoint_spec = spec.get("paths", {}).get(endpoint_path, {})

        if not endpoint_spec:
            raise ValueError(f"Endpoint {endpoint_path} not found in spec")

        # Collect methods and their schemas
        methods = {}
        all_properties = {}
        all_required = []

        for method in ["get", "post", "put", "patch", "delete"]:
            method_spec = endpoint_spec.get(method)
            if method_spec:
                methods[method] = method_spec.get("summary", "")

                # Extract request schema for POST/PUT/PATCH
                if method in ["post", "put", "patch"]:
                    request_body = method_spec.get("requestBody", {})
                    # Try both content types
                    content = request_body.get("content", {})
                    schema = (
                        content.get("application/x-www-form-urlencoded", {}).get("schema", {}) or
                        content.get("application/json", {}).get("schema", {})
                    )
                    if schema:
                        props = schema.get("properties", {})
                        all_properties.update(props)
                        all_required.extend(schema.get("required", []))

                # Extract query parameters for GET
                if method == "get":
                    parameters = method_spec.get("parameters", [])
                    for param in parameters:
                        if param.get("in") == "query":
                            param_name = param.get("name", "")
                            all_properties[param_name] = {
                                "description": param.get("description", ""),
                                "schema": param.get("schema", {}),
                                "required": param.get("required", False)
                            }
                            if param.get("required"):
                                all_required.append(param_name)

        # Return structured snapshot
        return {
            "endpoint": endpoint_path,
            "methods": methods,
            "schema": {"properties": all_properties, "required": list(set(all_required))},
            "properties": all_properties,
            "required": list(set(all_required))
        }

    async def get_all_endpoints_snapshots(self, spec_type: str = "stable") -> List[Dict[str, Any]]:
        """
        Get snapshots for all monitored endpoints

        Args:
            spec_type: One of 'stable', 'preview', or 'beta'

        Returns:
            List of endpoint snapshots
        """
        snapshots = []
        for endpoint_path in self.MONITORED_ENDPOINTS:
            try:
                snapshot = await self.get_endpoint_snapshot(endpoint_path, spec_type)
                snapshots.append(snapshot)
                logger.info(f"Captured snapshot for {endpoint_path} ({spec_type})")
            except ValueError as e:
                logger.warning(f"Skipping {endpoint_path}: {e}")
        return snapshots

    def get_monitored_endpoints(self) -> List[str]:
        """Return list of endpoints being monitored"""
        return self.MONITORED_ENDPOINTS.copy()