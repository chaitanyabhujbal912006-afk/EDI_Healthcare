"""
Read operations for ValidEDI custom configurations.

Provides functions to retrieve and list custom rules and code sets.
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any
import yaml

from ._exceptions import RuleNotFoundError


@dataclass
class ReadResult:
    """
    Result of a read operation.
    
    Attributes:
        rule_id: The rule or code set ID
        source_file: Path to the file containing this config
        raw_yaml: The raw YAML text for this config
        parsed_dict: The parsed configuration as a dictionary
        config_type: Type of configuration ("rule" or "code_set")
    """
    rule_id: str
    source_file: str
    raw_yaml: str
    parsed_dict: dict
    config_type: str


def get_custom_config(
    rule_id: Optional[str] = None,
    config_type: str = "rule",
    filters: Optional[dict] = None,
    config_dir: Optional[Path] = None
) -> list[ReadResult]:
    """
    Get custom configuration(s) by ID or filters.
    
    Args:
        rule_id: Specific rule/code_set ID to retrieve (if None, return all)
        config_type: Type of config ("rule" or "code_set")
        filters: Optional filters to apply (e.g., {"severity": "error"})
        config_dir: Path to config directory (defaults to validedi/config)
        
    Returns:
        List of ReadResult objects (single item if rule_id specified)
        
    Raises:
        RuleNotFoundError: If rule_id is specified but not found
        
    Example:
        # Get a specific rule
        results = get_custom_config(rule_id="CLM-001")
        
        # Get all error-severity rules
        results = get_custom_config(filters={"severity": "error"})
        
        # Get all rules
        results = get_custom_config()
    """
    # Determine config directory
    if config_dir is None:
        config_dir = Path(__file__).parent.parent / 'config'
    
    if config_type == "rule":
        target_dir = config_dir / 'rules'
    elif config_type == "code_set":
        target_dir = config_dir / 'code_sets'
    else:
        raise ValueError(f"Invalid config_type: {config_type}")
    
    if not target_dir.exists():
        return []
    
    results = []
    
    # Scan all YAML files
    for yaml_file in target_dir.glob('*.yaml'):
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                content = f.read()
                data = yaml.safe_load(content)
            
            if config_type == "rule":
                # Process rules
                for rule in data.get('rules', []):
                    if not isinstance(rule, dict) or 'id' not in rule:
                        continue
                    
                    # Check if this is the rule we're looking for
                    if rule_id and rule['id'] != rule_id:
                        continue
                    
                    # Apply filters
                    if filters and not _matches_filters(rule, filters):
                        continue
                    
                    # Extract raw YAML for this rule
                    raw_yaml = _extract_rule_yaml(content, rule['id'])
                    
                    results.append(ReadResult(
                        rule_id=rule['id'],
                        source_file=str(yaml_file),
                        raw_yaml=raw_yaml,
                        parsed_dict=rule,
                        config_type=config_type
                    ))
                    
                    # If we found the specific rule, we're done
                    if rule_id:
                        return results
            
            elif config_type == "code_set":
                # Process code set
                code_set_id = data.get('code_set_id')
                if not code_set_id:
                    continue
                
                # Check if this is the code set we're looking for
                if rule_id and code_set_id != rule_id:
                    continue
                
                # Apply filters
                if filters and not _matches_filters(data, filters):
                    continue
                
                results.append(ReadResult(
                    rule_id=code_set_id,
                    source_file=str(yaml_file),
                    raw_yaml=content,
                    parsed_dict=data,
                    config_type=config_type
                ))
                
                # If we found the specific code set, we're done
                if rule_id:
                    return results
        
        except Exception:
            # Skip files that can't be parsed
            continue
    
    # If we were looking for a specific ID and didn't find it, raise error
    if rule_id and not results:
        raise RuleNotFoundError(rule_id, config_type)
    
    return results


def list_rule_ids(
    config_type: str = "rule",
    config_dir: Optional[Path] = None
) -> list[tuple[str, str]]:
    """
    List all rule/code_set IDs and their source files.
    
    Args:
        config_type: Type of config ("rule" or "code_set")
        config_dir: Path to config directory (defaults to validedi/config)
        
    Returns:
        List of (rule_id, source_file) tuples
        
    Example:
        ids = list_rule_ids()
        for rule_id, source_file in ids:
            print(f"{rule_id} -> {source_file}")
    """
    results = get_custom_config(config_type=config_type, config_dir=config_dir)
    return [(r.rule_id, r.source_file) for r in results]


def _matches_filters(config: dict, filters: dict) -> bool:
    """Check if a configuration matches the given filters."""
    for key, value in filters.items():
        if key not in config:
            return False
        if config[key] != value:
            return False
    return True


def _extract_rule_yaml(content: str, rule_id: str) -> str:
    """
    Extract the YAML text for a specific rule from file content.
    
    This is a best-effort extraction that finds the rule block.
    """
    lines = content.split('\n')
    rule_lines = []
    in_rule = False
    indent_level = None
    
    for i, line in enumerate(lines):
        # Look for the rule ID
        if f"id: '{rule_id}'" in line or f'id: "{rule_id}"' in line or f"id: {rule_id}" in line:
            # Find the start of this rule (the "- id:" line or just before)
            start_idx = i
            # Look backwards for the list item marker
            for j in range(i, max(0, i - 5), -1):
                if lines[j].strip().startswith('- id:'):
                    start_idx = j
                    break
            
            # Determine indent level
            indent_level = len(lines[start_idx]) - len(lines[start_idx].lstrip())
            in_rule = True
            
            # Add lines from start
            for j in range(start_idx, i + 1):
                rule_lines.append(lines[j])
            continue
        
        if in_rule:
            # Check if we've reached the next rule or end of rules section
            stripped = line.strip()
            
            # Empty lines are part of the rule
            if not stripped:
                rule_lines.append(line)
                continue
            
            # Check indent level
            current_indent = len(line) - len(line.lstrip())
            
            # If we hit another list item at same level, we're done
            if stripped.startswith('- ') and current_indent == indent_level:
                break
            
            # If indent is less than or equal to rule indent and not empty, we're done
            if current_indent <= indent_level and stripped and not stripped.startswith('#'):
                break
            
            # Otherwise, this line is part of the rule
            rule_lines.append(line)
    
    return '\n'.join(rule_lines).strip()
