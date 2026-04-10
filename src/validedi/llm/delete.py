"""
Delete operations for ValidEDI custom configurations.

Provides functions to delete existing rules and code sets.
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import yaml
import shutil

from .read import get_custom_config
from ._exceptions import RuleNotFoundError


@dataclass
class DeleteResult:
    """
    Result of a delete operation.
    
    Attributes:
        success: Whether the delete was successful
        rule_id: The rule or code set ID that was deleted
        deleted_yaml: The YAML that was deleted
        source_file: Path to the file that was modified
        validation_errors: List of errors (empty if successful)
        backup_path: Path to backup file (if created)
    """
    success: bool
    rule_id: str
    deleted_yaml: str
    source_file: str
    validation_errors: list[str]
    backup_path: Optional[str] = None
    
    def __str__(self) -> str:
        if self.success:
            return f"✅ Successfully deleted {self.rule_id} from {self.source_file}"
        else:
            errors = "\n".join(f"  - {err}" for err in self.validation_errors)
            return f"❌ Failed to delete {self.rule_id}:\n{errors}"


def delete_custom_config(
    rule_id: str,
    config_type: str = "rule",
    dry_run: bool = False,
    create_backups: bool = True,
    config_dir: Optional[Path] = None
) -> DeleteResult:
    """
    Delete an existing custom configuration.
    
    Args:
        rule_id: The ID of the rule/code_set to delete
        config_type: Type of config ("rule" or "code_set")
        dry_run: If True, return what would be deleted without modifying files
        create_backups: Whether to create backup files before modifying
        config_dir: Path to config directory (defaults to validedi/config)
        
    Returns:
        DeleteResult with operation details
        
    Raises:
        RuleNotFoundError: If rule_id is not found
        
    Example:
        result = delete_custom_config(rule_id="CLM-001")
        
        if result.success:
            print(f"✅ Deleted {result.rule_id}")
        else:
            print(f"❌ Errors: {result.validation_errors}")
    """
    # Determine config directory
    if config_dir is None:
        config_dir = Path(__file__).parent.parent / 'config'
    
    try:
        # Step 1: Locate the rule
        results = get_custom_config(
            rule_id=rule_id,
            config_type=config_type,
            config_dir=config_dir
        )
        
        if not results:
            raise RuleNotFoundError(rule_id, config_type)
        
        existing = results[0]
        deleted_yaml = existing.raw_yaml
        source_file = Path(existing.source_file)
        
        # Step 2: If dry_run, return without modifying
        if dry_run:
            return DeleteResult(
                success=True,
                rule_id=rule_id,
                deleted_yaml=deleted_yaml,
                source_file=str(source_file),
                validation_errors=[]
            )
        
        # Step 3: Create backup if needed
        backup_path = None
        if create_backups:
            backup_path = _create_backup(source_file)
        
        # Step 4: Remove the rule from the file
        _remove_rule_from_file(
            source_file=source_file,
            rule_id=rule_id,
            config_type=config_type
        )
        
        # Step 5: Invalidate cache
        try:
            from validedi.engine.config_loader import invalidate_cache
            invalidate_cache()
        except:
            pass  # Cache invalidation is optional
        
        return DeleteResult(
            success=True,
            rule_id=rule_id,
            deleted_yaml=deleted_yaml,
            source_file=str(source_file),
            validation_errors=[],
            backup_path=backup_path
        )
    
    except RuleNotFoundError:
        raise
    except Exception as e:
        return DeleteResult(
            success=False,
            rule_id=rule_id,
            deleted_yaml=deleted_yaml if 'deleted_yaml' in locals() else "",
            source_file=str(source_file) if 'source_file' in locals() else "",
            validation_errors=[f"Unexpected error: {str(e)}"]
        )


def _create_backup(target_path: Path) -> str:
    """Create a backup of the target file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = target_path.parent / f"{target_path.stem}_backup_{timestamp}{target_path.suffix}"
    shutil.copy2(target_path, backup_path)
    return str(backup_path)


def _remove_rule_from_file(
    source_file: Path,
    rule_id: str,
    config_type: str
) -> None:
    """Remove a rule from the file."""
    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse the file
    data = yaml.safe_load(content)
    
    if config_type == "rule":
        # Find and remove the rule from the list
        rules = data.get('rules', [])
        data['rules'] = [rule for rule in rules if rule.get('id') != rule_id]
    
    elif config_type == "code_set":
        # For code sets, if this is the only code set in the file, we could delete the file
        # But for safety, we'll just clear the content or raise an error
        # Since code set files typically contain one code set, deleting means removing the file
        # For now, let's just clear it to be safe
        if data.get('code_set_id') == rule_id:
            # Option 1: Delete the file entirely
            source_file.unlink()
            return
    
    # Write back to file
    with open(source_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
