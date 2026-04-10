"""
Update operations for ValidEDI custom configurations.

Provides functions to update existing rules and code sets using LLM.
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional
from datetime import datetime
import yaml
import shutil

from .read import get_custom_config
from ._exceptions import RuleNotFoundError, RuleConflictError
from ._validation import check_id_conflict


# Type alias for LLM callable
LLMCallable = Callable[[str], str]


@dataclass
class UpdateResult:
    """
    Result of an update operation.
    
    Attributes:
        success: Whether the update was successful
        rule_id: The rule or code set ID that was updated
        old_yaml: The original YAML before update
        new_yaml: The new YAML after update
        source_file: Path to the file that was updated
        validation_errors: List of validation errors (empty if valid)
        backup_path: Path to backup file (if created)
    """
    success: bool
    rule_id: str
    old_yaml: str
    new_yaml: str
    source_file: str
    validation_errors: list[str]
    backup_path: Optional[str] = None
    
    def __str__(self) -> str:
        if self.success:
            return f"✅ Successfully updated {self.rule_id} in {self.source_file}"
        else:
            errors = "\n".join(f"  - {err}" for err in self.validation_errors)
            return f"❌ Failed to update {self.rule_id}:\n{errors}"


def update_custom_config(
    rule_id: str,
    context: str,
    llm: LLMCallable,
    config_type: str = "rule",
    dry_run: bool = False,
    create_backups: bool = True,
    config_dir: Optional[Path] = None
) -> UpdateResult:
    """
    Update an existing custom configuration using natural language.
    
    Args:
        rule_id: The ID of the rule/code_set to update
        context: Natural language description of the changes
        llm: LLM callable that takes a prompt and returns a response
        config_type: Type of config ("rule" or "code_set")
        dry_run: If True, validate but don't write files
        create_backups: Whether to create backup files before modifying
        config_dir: Path to config directory (defaults to validedi/config)
        
    Returns:
        UpdateResult with operation details
        
    Raises:
        RuleNotFoundError: If rule_id is not found
        
    Example:
        result = update_custom_config(
            rule_id="CLM-001",
            context="Change severity to warning and update message",
            llm=your_llm_callable
        )
        
        if result.success:
            print(f"✅ Updated {result.rule_id}")
        else:
            print(f"❌ Errors: {result.validation_errors}")
    """
    # Determine config directory
    if config_dir is None:
        config_dir = Path(__file__).parent.parent / 'config'
    
    try:
        # Step 1: Locate the existing rule
        results = get_custom_config(
            rule_id=rule_id,
            config_type=config_type,
            config_dir=config_dir
        )
        
        if not results:
            raise RuleNotFoundError(rule_id, config_type)
        
        existing = results[0]
        old_yaml = existing.raw_yaml
        source_file = Path(existing.source_file)
        
        # Step 2: Generate updated YAML using LLM
        new_yaml = _generate_updated_yaml(
            existing_yaml=old_yaml,
            context=context,
            llm=llm,
            config_type=config_type
        )
        
        if not new_yaml:
            return UpdateResult(
                success=False,
                rule_id=rule_id,
                old_yaml=old_yaml,
                new_yaml="",
                source_file=str(source_file),
                validation_errors=["LLM failed to generate valid YAML"]
            )
        
        # Step 3: Validate the updated YAML
        validation_errors = _validate_updated_yaml(
            new_yaml=new_yaml,
            rule_id=rule_id,
            config_type=config_type,
            source_file=source_file.name,
            config_dir=config_dir
        )
        
        if validation_errors:
            return UpdateResult(
                success=False,
                rule_id=rule_id,
                old_yaml=old_yaml,
                new_yaml=new_yaml,
                source_file=str(source_file),
                validation_errors=validation_errors
            )
        
        # Step 4: If dry_run, return without writing
        if dry_run:
            return UpdateResult(
                success=True,
                rule_id=rule_id,
                old_yaml=old_yaml,
                new_yaml=new_yaml,
                source_file=str(source_file),
                validation_errors=[]
            )
        
        # Step 5: Create backup if needed
        backup_path = None
        if create_backups:
            backup_path = _create_backup(source_file)
        
        # Step 6: Replace the rule in-place
        _replace_rule_in_file(
            source_file=source_file,
            rule_id=rule_id,
            new_yaml=new_yaml,
            config_type=config_type
        )
        
        # Step 7: Invalidate cache
        try:
            from validedi.engine.config_loader import invalidate_cache
            invalidate_cache()
        except:
            pass  # Cache invalidation is optional
        
        return UpdateResult(
            success=True,
            rule_id=rule_id,
            old_yaml=old_yaml,
            new_yaml=new_yaml,
            source_file=str(source_file),
            validation_errors=[],
            backup_path=backup_path
        )
    
    except RuleNotFoundError:
        raise
    except Exception as e:
        return UpdateResult(
            success=False,
            rule_id=rule_id,
            old_yaml=old_yaml if 'old_yaml' in locals() else "",
            new_yaml=new_yaml if 'new_yaml' in locals() else "",
            source_file=str(source_file) if 'source_file' in locals() else "",
            validation_errors=[f"Unexpected error: {str(e)}"]
        )


def _generate_updated_yaml(
    existing_yaml: str,
    context: str,
    llm: LLMCallable,
    config_type: str
) -> str:
    """Generate updated YAML using LLM."""
    prompt = f"""You are updating a YAML configuration for the validedi EDI validation system.

EXISTING CONFIGURATION:
```yaml
{existing_yaml}
```

REQUESTED CHANGES:
{context}

INSTRUCTIONS:
1. Apply the requested changes to the existing configuration
2. Preserve the same ID - DO NOT change the rule/code_set ID
3. Maintain the same structure and format
4. Output ONLY the updated YAML - no explanations, no markdown blocks
5. Ensure all required fields remain present
6. Use 2-space indentation consistently
7. For rules: start with "- id:" (list item format)
8. For code sets: start with "code_set_id:"

Generate the updated YAML configuration now:"""
    
    try:
        response = llm(prompt).strip()
        # Clean up response
        response = _clean_llm_response(response)
        return response
    except Exception:
        return ""


def _validate_updated_yaml(
    new_yaml: str,
    rule_id: str,
    config_type: str,
    source_file: str,
    config_dir: Path
) -> list[str]:
    """Validate the updated YAML."""
    errors = []
    
    # 1. Check if YAML is parseable
    try:
        parsed = yaml.safe_load(new_yaml)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML syntax: {str(e)}")
        return errors
    
    # 2. Ensure ID hasn't changed
    if config_type == "rule":
        if isinstance(parsed, dict):
            actual_id = parsed.get('id')
        elif isinstance(parsed, list) and len(parsed) > 0:
            actual_id = parsed[0].get('id')
        else:
            errors.append("Invalid rule structure after update")
            return errors
        
        if actual_id != rule_id:
            errors.append(f"Rule ID changed from '{rule_id}' to '{actual_id}' - ID must remain the same")
    
    elif config_type == "code_set":
        actual_id = parsed.get('code_set_id')
        if actual_id != rule_id:
            errors.append(f"Code set ID changed from '{rule_id}' to '{actual_id}' - ID must remain the same")
    
    # 3. Validate structure (reuse validation from config_updater)
    if config_type == "rule":
        errors.extend(_validate_rule_structure(parsed))
    elif config_type == "code_set":
        errors.extend(_validate_code_set_structure(parsed))
    
    return errors


def _validate_rule_structure(parsed) -> list[str]:
    """Validate rule structure (simplified version)."""
    errors = []
    
    # Handle different structures
    if isinstance(parsed, dict):
        rules = [parsed]
    elif isinstance(parsed, list):
        rules = parsed
    else:
        return [f"Invalid rule structure: expected dict or list"]
    
    for rule in rules:
        if not isinstance(rule, dict):
            errors.append("Rule must be a dictionary")
            continue
        
        # Required fields
        if 'id' not in rule:
            errors.append("Rule missing required field: 'id'")
        if 'type' not in rule:
            errors.append("Rule missing required field: 'type'")
        if 'severity' not in rule:
            errors.append("Rule missing required field: 'severity'")
        elif rule['severity'] not in ('error', 'warning', 'info'):
            errors.append(f"Invalid severity: '{rule['severity']}'")
        if 'message' not in rule:
            errors.append("Rule missing required field: 'message'")
    
    return errors


def _validate_code_set_structure(parsed) -> list[str]:
    """Validate code set structure (simplified version)."""
    errors = []
    
    if not isinstance(parsed, dict):
        return ["Code set must be a dictionary"]
    
    if 'code_set_id' not in parsed:
        errors.append("Code set missing required field: 'code_set_id'")
    if 'description' not in parsed:
        errors.append("Code set missing required field: 'description'")
    if 'codes' not in parsed:
        errors.append("Code set missing required field: 'codes'")
    
    return errors


def _clean_llm_response(response: str) -> str:
    """Clean LLM response to extract pure YAML."""
    import re
    
    # Remove markdown code blocks
    response = re.sub(r'```ya?ml\s*\n', '', response)
    response = re.sub(r'```\s*$', '', response)
    response = response.strip()
    
    return response


def _create_backup(target_path: Path) -> str:
    """Create a backup of the target file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = target_path.parent / f"{target_path.stem}_backup_{timestamp}{target_path.suffix}"
    shutil.copy2(target_path, backup_path)
    return str(backup_path)


def _replace_rule_in_file(
    source_file: Path,
    rule_id: str,
    new_yaml: str,
    config_type: str
) -> None:
    """Replace a rule in-place in the file."""
    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse the file
    data = yaml.safe_load(content)
    
    # Parse the new YAML
    new_data = yaml.safe_load(new_yaml)
    
    if config_type == "rule":
        # Normalize new_data to dict
        if isinstance(new_data, list):
            new_rule = new_data[0]
        else:
            new_rule = new_data
        
        # Find and replace the rule in the list
        rules = data.get('rules', [])
        for i, rule in enumerate(rules):
            if rule.get('id') == rule_id:
                rules[i] = new_rule
                break
        
        data['rules'] = rules
    
    elif config_type == "code_set":
        # For code sets, replace the entire file content
        data = new_data
    
    # Write back to file
    with open(source_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
