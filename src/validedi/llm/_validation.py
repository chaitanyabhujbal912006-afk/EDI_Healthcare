"""
Internal validation utilities for LLM config operations.

Handles global ID uniqueness checks and other validation logic.
"""

from pathlib import Path
from typing import Optional
import yaml


def get_all_rule_ids(rules_dir: Path) -> dict[str, str]:
    """
    Scan all YAML files in rules directory and collect all rule IDs.
    
    Args:
        rules_dir: Path to rules directory
        
    Returns:
        Dict mapping rule_id -> source_file
    """
    all_ids = {}
    
    if not rules_dir.exists():
        return all_ids
    
    for rule_file in rules_dir.glob('*.yaml'):
        try:
            with open(rule_file, 'r', encoding='utf-8') as f:
                rule_data = yaml.safe_load(f)
            
            for rule in rule_data.get('rules', []):
                if 'id' in rule:
                    all_ids[rule['id']] = rule_file.name
        except Exception:
            # Skip files that can't be parsed
            continue
    
    return all_ids


def get_all_code_set_ids(code_sets_dir: Path) -> dict[str, str]:
    """
    Scan all YAML files in code_sets directory and collect all code set IDs.
    
    Args:
        code_sets_dir: Path to code_sets directory
        
    Returns:
        Dict mapping code_set_id -> source_file
    """
    all_ids = {}
    
    if not code_sets_dir.exists():
        return all_ids
    
    for code_file in code_sets_dir.glob('*.yaml'):
        try:
            with open(code_file, 'r', encoding='utf-8') as f:
                code_data = yaml.safe_load(f)
            
            code_set_id = code_data.get('code_set_id')
            if code_set_id:
                all_ids[code_set_id] = code_file.name
        except Exception:
            # Skip files that can't be parsed
            continue
    
    return all_ids


def check_id_conflict(
    rule_id: str,
    config_type: str,
    rules_dir: Path,
    code_sets_dir: Path,
    exclude_file: Optional[str] = None
) -> Optional[str]:
    """
    Check if a rule/code_set ID conflicts with existing IDs globally.
    
    Args:
        rule_id: The ID to check
        config_type: "rule" or "code_set"
        rules_dir: Path to rules directory
        code_sets_dir: Path to code_sets directory
        exclude_file: Optional filename to exclude from check (for updates)
        
    Returns:
        Conflict message if ID exists, None otherwise
    """
    if config_type == "rule":
        all_ids = get_all_rule_ids(rules_dir)
    elif config_type == "code_set":
        all_ids = get_all_code_set_ids(code_sets_dir)
    else:
        return None
    
    if rule_id in all_ids:
        source_file = all_ids[rule_id]
        # If this is the file we're updating, it's not a conflict
        if exclude_file and source_file == exclude_file:
            return None
        return f"ID '{rule_id}' already exists in {source_file}"
    
    return None
