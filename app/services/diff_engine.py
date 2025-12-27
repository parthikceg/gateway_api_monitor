"""Schema comparison and diff engine"""
from typing import Dict, Any, List, Tuple
import json
import logging

logger = logging.getLogger(__name__)


class DiffEngine:
    """Compares two API schemas and identifies changes"""
    
    def compare_schemas(
        self, 
        old_schema: Dict[str, Any], 
        new_schema: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Compare two schemas and return list of changes"""
        changes = []
        
        # Compare properties
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        
        # Find new properties
        for prop_name, prop_def in new_props.items():
            if prop_name not in old_props:
                changes.append({
                    "change_type": "property_added",
                    "field_path": f"properties.{prop_name}",
                    "old_value": None,
                    "new_value": prop_def,
                    "severity": self._determine_severity("added", prop_def)
                })
        
        # Find removed properties
        for prop_name, prop_def in old_props.items():
            if prop_name not in new_props:
                changes.append({
                    "change_type": "property_removed",
                    "field_path": f"properties.{prop_name}",
                    "old_value": prop_def,
                    "new_value": None,
                    "severity": "high"  # Removals are usually breaking
                })
        
        # Find modified properties
        for prop_name in old_props.keys():
            if prop_name in new_props:
                prop_changes = self._compare_property(
                    prop_name, 
                    old_props[prop_name], 
                    new_props[prop_name]
                )
                changes.extend(prop_changes)
        
        # Compare required fields
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))
        
        # New required fields
        for field in new_required - old_required:
            changes.append({
                "change_type": "field_now_required",
                "field_path": f"required.{field}",
                "old_value": False,
                "new_value": True,
                "severity": "high"  # Making field required is breaking
            })
        
        # Fields no longer required
        for field in old_required - new_required:
            changes.append({
                "change_type": "field_no_longer_required",
                "field_path": f"required.{field}",
                "old_value": True,
                "new_value": False,
                "severity": "low"  # Making field optional is safe
            })
        
        return changes
    
    def _compare_property(
        self, 
        prop_name: str, 
        old_prop: Dict[str, Any], 
        new_prop: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Compare two property definitions"""
        changes = []
        
        # Check type changes
        old_type = old_prop.get("type")
        new_type = new_prop.get("type")
        
        if old_type != new_type:
            changes.append({
                "change_type": "type_changed",
                "field_path": f"properties.{prop_name}.type",
                "old_value": old_type,
                "new_value": new_type,
                "severity": "high"  # Type changes are usually breaking
            })
        
        # Check description changes
        old_desc = old_prop.get("description", "")
        new_desc = new_prop.get("description", "")
        
        if old_desc != new_desc:
            changes.append({
                "change_type": "description_changed",
                "field_path": f"properties.{prop_name}.description",
                "old_value": old_desc,
                "new_value": new_desc,
                "severity": "info"  # Documentation changes are informational
            })
        
        # Check enum changes
        old_enum = old_prop.get("enum", [])
        new_enum = new_prop.get("enum", [])
        
        if old_enum != new_enum:
            added_values = set(new_enum) - set(old_enum)
            removed_values = set(old_enum) - set(new_enum)
            
            if added_values:
                changes.append({
                    "change_type": "enum_values_added",
                    "field_path": f"properties.{prop_name}.enum",
                    "old_value": old_enum,
                    "new_value": new_enum,
                    "severity": "low"
                })
            
            if removed_values:
                changes.append({
                    "change_type": "enum_values_removed",
                    "field_path": f"properties.{prop_name}.enum",
                    "old_value": old_enum,
                    "new_value": new_enum,
                    "severity": "medium"
                })
        
        return changes
    
    def _determine_severity(self, change_type: str, prop_def: Dict[str, Any]) -> str:
        """Determine severity of a change"""
        # New optional properties are low severity
        if change_type == "added":
            return "low"
        
        # Removals are high severity
        if change_type == "removed":
            return "high"
        
        return "medium"
