"""Stripe API crawler service"""
import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class StripeCrawler:
    """Fetches Stripe API specifications from GitHub"""

    def __init__(self):
        self._spec_cache: Dict[str, Dict[str, Any]] = {}

    # Stripe OpenAPI spec URLs - Multi-tier
    SPEC_URLS = {
        "stable": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json",
        "preview": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.sdk.json",
        "beta": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.beta.sdk.json"
    }

    # Endpoints to monitor - organized by priority
    # Priority 1: Core Payment Processing
    MONITORED_ENDPOINTS = [
        "/v1/payment_intents",
        "/v1/charges",
        "/v1/payment_methods",
    ]

    # Priority 2: Additional Payment Endpoints (can be enabled later)
    # ADDITIONAL_ENDPOINTS = [
    #     "/v1/refunds",
    #     "/v1/customers",
    #     "/v1/checkout/sessions",
    #     "/v1/setup_intents",
    #     "/v1/payment_links",
    # ]

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
        Fetch OpenAPI specification from Stripe (cached per tier)

        Args:
            spec_type: One of 'stable', 'preview', or 'beta'
        """
        # Return cached spec if already downloaded this session
        if spec_type in self._spec_cache:
            logger.info(f"Using cached {spec_type} spec")
            return self._spec_cache[spec_type]

        url = self.SPEC_URLS.get(spec_type)
        if not url:
            raise ValueError(f"Invalid spec_type: {spec_type}")

        logger.info(f"Fetching {spec_type} spec from: {url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            spec = response.json()

        self._spec_cache[spec_type] = spec
        return spec
    
    async def get_payment_intents_snapshot(self, spec_type: str = "stable") -> Dict[str, Any]:
        """
        Extract Payment Intents endpoint schema from spec (legacy method for backwards compatibility)

        Args:
            spec_type: One of 'stable', 'preview', or 'beta'
        """
        return await self.get_endpoint_snapshot("/v1/payment_intents", spec_type)

    def _resolve_ref(self, spec: Dict[str, Any], ref: str) -> Dict[str, Any]:
        """
        Resolve a $ref reference in the OpenAPI spec

        Args:
            spec: The full OpenAPI spec
            ref: The reference string (e.g., "#/components/schemas/charge")

        Returns:
            The resolved schema
        """
        if not ref.startswith("#/"):
            return {}

        # Parse the reference path
        parts = ref[2:].split("/")  # Remove "#/" and split
        result = spec
        for part in parts:
            result = result.get(part, {})
            if not result:
                return {}
        return result

    def _expand_schema(self, spec: Dict[str, Any], schema: Any, depth: int = 0) -> Dict[str, Any]:
        """
        Expand a schema by resolving $ref references (shallow — one level only).
        Used for diff engine compatibility where we don't need deep nesting.
        """
        if not schema or not isinstance(schema, dict):
            return schema if isinstance(schema, dict) else {}

        if depth > 5:
            return schema

        if "$ref" in schema:
            resolved = self._resolve_ref(spec, schema["$ref"])
            if resolved:
                return self._expand_schema(spec, resolved, depth + 1)
            return schema

        for key in ["anyOf", "oneOf"]:
            if key in schema and isinstance(schema[key], list):
                for option in schema[key]:
                    if isinstance(option, dict) and option.get("type") != "null" and "$ref" in option:
                        resolved = self._resolve_ref(spec, option["$ref"])
                        if resolved:
                            return self._expand_schema(spec, resolved, depth + 1)
                for option in schema[key]:
                    if isinstance(option, dict) and option.get("type") != "null":
                        return self._expand_schema(spec, option, depth + 1)

        return schema

    # Max nesting depth for deep expansion of child attributes.
    # Even with expandable objects skipped, child attributes like
    # payment_method_options have many sub-schemas. Depth 3 keeps
    # expansion fast (<1 min per endpoint) while showing 3 levels of nesting.
    MAX_EXPAND_DEPTH = 3

    def _deep_expand_properties(self, spec: Dict[str, Any], schema: Dict[str, Any],
                                 depth: int = 0, visited_refs: Optional[frozenset] = None) -> Dict[str, Any]:
        """
        Recursively expand all properties within a schema, resolving nested $ref at every level.
        This produces a fully resolved tree that the frontend can render with nested expand/collapse.
        """
        if visited_refs is None:
            visited_refs = frozenset()
        if depth > self.MAX_EXPAND_DEPTH or not isinstance(schema, dict):
            return schema if isinstance(schema, dict) else {}

        result = dict(schema)  # shallow copy

        # Expand each property recursively
        if "properties" in result and isinstance(result["properties"], dict):
            expanded_props = {}
            for prop_name, prop_schema in result["properties"].items():
                if isinstance(prop_schema, dict):
                    expanded_props[prop_name] = self._expand_and_recurse(spec, prop_schema, depth + 1, visited_refs)
                else:
                    expanded_props[prop_name] = prop_schema
            result["properties"] = expanded_props

        # Expand items (for array types like data: [PaymentIntent, ...])
        if "items" in result and isinstance(result["items"], dict):
            result["items"] = self._expand_and_recurse(spec, result["items"], depth + 1, visited_refs)

        return result

    def _expand_and_recurse(self, spec: Dict[str, Any], schema: Dict[str, Any],
                             depth: int = 0, visited_refs: Optional[frozenset] = None) -> Dict[str, Any]:
        """
        Resolve $ref/anyOf/oneOf, then deep-expand the resolved schema's properties.
        Tracks visited $refs to prevent infinite loops from circular references.
        """
        if visited_refs is None:
            visited_refs = frozenset()
        if not isinstance(schema, dict) or depth > self.MAX_EXPAND_DEPTH:
            return schema if isinstance(schema, dict) else {}

        # Handle $ref with circular reference detection
        if "$ref" in schema:
            ref = schema["$ref"]
            if ref in visited_refs:
                ref_name = ref.split("/")[-1]
                return {"type": "object", "description": f"(circular ref: {ref_name})"}
            new_visited = visited_refs | {ref}
            resolved = self._resolve_ref(spec, ref)
            if resolved:
                return self._deep_expand_properties(spec, resolved, depth, new_visited)
            return schema

        # Handle anyOf/oneOf — distinguish expandable objects from child attributes
        for key in ["anyOf", "oneOf"]:
            if key in schema and isinstance(schema[key], list):
                options = schema[key]
                has_string_option = any(
                    isinstance(o, dict) and o.get("type") == "string"
                    for o in options
                )
                ref_option = next(
                    (o for o in options if isinstance(o, dict) and "$ref" in o and o.get("type") != "null"),
                    None
                )

                if has_string_option and ref_option:
                    # EXPANDABLE OBJECT: anyOf[string, $ref] — this is a foreign key
                    # (e.g., customer can be "cus_123" or expanded Customer object)
                    # Don't deep-expand — just show as string with expandable marker
                    ref_name = ref_option["$ref"].split("/")[-1]
                    result = {
                        "type": "string",
                        "description": schema.get("description", ""),
                        "_expandable": True,
                        "_expandable_type": ref_name,
                    }
                    # Preserve nullable
                    if any(isinstance(o, dict) and o.get("type") == "null" for o in options):
                        result["nullable"] = True
                    return result

                # CHILD ATTRIBUTE: anyOf[$ref] without string — inline sub-object
                if ref_option:
                    resolved = self._expand_and_recurse(spec, ref_option, depth, visited_refs)
                    # Preserve parent description if resolved schema lacks one
                    if isinstance(resolved, dict) and not resolved.get("description") and schema.get("description"):
                        resolved = dict(resolved)
                        resolved["description"] = schema["description"]
                    return resolved

                # Fallback: first non-null option
                for option in options:
                    if isinstance(option, dict) and option.get("type") != "null":
                        resolved = self._expand_and_recurse(spec, option, depth, visited_refs)
                        if isinstance(resolved, dict) and not resolved.get("description") and schema.get("description"):
                            resolved = dict(resolved)
                            resolved["description"] = schema["description"]
                        return resolved

        # No $ref — but might have nested properties/items that need expansion
        return self._deep_expand_properties(spec, schema, depth, visited_refs)

    async def get_endpoint_snapshot(self, endpoint_path: str, spec_type: str = "stable") -> Dict[str, Any]:
        """
        Extract endpoint schema from spec for any given endpoint.
        Captures BOTH request parameters AND response schema.
        Runs CPU-bound schema expansion in a thread pool to keep the event loop responsive.

        Args:
            endpoint_path: The API endpoint path (e.g., "/v1/payment_intents")
            spec_type: One of 'stable', 'preview', or 'beta'
        """
        spec = await self.fetch_spec(spec_type)

        # Run CPU-bound schema expansion in a thread so the event loop stays responsive
        return await asyncio.to_thread(self._build_endpoint_snapshot, spec, endpoint_path)

    def _build_endpoint_snapshot(self, spec: Dict[str, Any], endpoint_path: str) -> Dict[str, Any]:
        """CPU-bound: extract and expand endpoint schema from the OpenAPI spec."""
        # Extract endpoint
        endpoint_spec = spec.get("paths", {}).get(endpoint_path, {})

        if not endpoint_spec:
            raise ValueError(f"Endpoint {endpoint_path} not found in spec")

        # Collect methods and their schemas
        methods = {}
        all_properties = {}
        all_required = []

        # Separate tracking for request vs response vs generic object
        request_properties = {}
        response_properties = {}
        object_properties = {}
        object_required = []
        object_ref = None  # Track the $ref to the component schema

        for method in ["get", "post", "put", "patch", "delete"]:
            method_spec = endpoint_spec.get(method)
            if method_spec:
                methods[method] = method_spec.get("summary", "")

                # ===== EXTRACT REQUEST SCHEMA (new features, parameters) =====
                # For POST/PUT/PATCH - get request body
                if method in ["post", "put", "patch"]:
                    request_body = method_spec.get("requestBody", {})
                    content = request_body.get("content", {})
                    schema = (
                        content.get("application/x-www-form-urlencoded", {}).get("schema", {}) or
                        content.get("application/json", {}).get("schema", {})
                    )
                    if schema:
                        expanded = self._expand_schema(spec, schema)
                        props = expanded.get("properties", {})
                        for prop_name, prop_schema in props.items():
                            expanded_prop = self._expand_and_recurse(spec, prop_schema)
                            expanded_prop["_schema_type"] = "request"
                            request_properties[f"request.{prop_name}"] = expanded_prop
                        all_required.extend([f"request.{r}" for r in expanded.get("required", [])])

                # For GET - get query parameters
                if method == "get":
                    parameters = method_spec.get("parameters", [])
                    for param in parameters:
                        if param.get("in") == "query":
                            param_name = param.get("name", "")
                            param_schema = param.get("schema", {})
                            expanded_param = self._expand_and_recurse(spec, param_schema)
                            request_properties[f"request.{param_name}"] = {
                                "description": param.get("description", ""),
                                "type": expanded_param.get("type", param_schema.get("type", "unknown")),
                                "_schema_type": "request",
                                **expanded_param
                            }
                            if param.get("required"):
                                all_required.append(f"request.{param_name}")

                # ===== EXTRACT RESPONSE SCHEMA (object structure, potential breaking changes) =====
                responses = method_spec.get("responses", {})
                success_response = responses.get("200", {})
                content = success_response.get("content", {})
                response_schema = content.get("application/json", {}).get("schema", {})

                if response_schema:
                    expanded = self._expand_schema(spec, response_schema)
                    props = expanded.get("properties", {})
                    for prop_name, prop_schema in props.items():
                        expanded_prop = self._expand_and_recurse(spec, prop_schema)
                        expanded_prop["_schema_type"] = "response"
                        response_properties[f"response.{prop_name}"] = expanded_prop
                    # Note: response required fields NOT added to all_required
                    # — object required fields are used instead (added below)

                    # ===== EXTRACT GENERIC OBJECT SCHEMA (the API object like PaymentIntent) =====
                    # Try to find the component schema $ref
                    if not object_ref:
                        raw_response_schema = content.get("application/json", {}).get("schema", {})
                        if "$ref" in raw_response_schema:
                            # POST/PUT/PATCH: direct $ref to component schema
                            object_ref = raw_response_schema["$ref"]
                        elif "properties" in raw_response_schema or "properties" in expanded:
                            # GET list endpoint: look for data.items.$ref
                            data_prop = raw_response_schema.get("properties", {}).get("data", {})
                            if not data_prop:
                                data_prop = expanded.get("properties", {}).get("data", {})
                            items = data_prop.get("items", {})
                            if "$ref" in items:
                                object_ref = items["$ref"]

        # ===== RESOLVE GENERIC OBJECT from component schema =====
        if object_ref:
            resolved_object = self._resolve_ref(spec, object_ref)
            if resolved_object and isinstance(resolved_object, dict):
                obj_props = resolved_object.get("properties", {})
                object_required = resolved_object.get("required", [])
                for prop_name, prop_schema in obj_props.items():
                    expanded_prop = self._expand_and_recurse(spec, prop_schema, 0, frozenset({object_ref}))
                    object_properties[prop_name] = expanded_prop

        # Build object properties with "object." prefix for diff tracking
        prefixed_object_properties = {}
        for prop_name, prop_schema in object_properties.items():
            prefixed_object_properties[f"object.{prop_name}"] = prop_schema

        # Merge request + object into all_properties (used by diff engine)
        all_properties.update(request_properties)
        all_properties.update(prefixed_object_properties)

        # Add object required fields
        all_required.extend([f"object.{r}" for r in object_required])

        # Return structured snapshot with object and request
        return {
            "endpoint": endpoint_path,
            "methods": methods,
            "schema": {"properties": all_properties, "required": list(set(all_required))},
            "properties": all_properties,
            "required": list(set(all_required)),
            # Separate access for each view
            "object_properties": object_properties,
            "object_required": object_required,
            "request_properties": request_properties,
            "response_properties": response_properties
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