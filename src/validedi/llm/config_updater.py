"""
LLM-powered configuration updater for validedi.

Allows administrators to add custom rules and code sets using natural language,
with the LLM translating intent into properly formatted YAML configuration.
"""

from __future__ import annotations
import os
import re
import yaml
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Optional, Any
from datetime import datetime

from .config_prompts import (
    build_config_generation_prompt,
    build_config_type_detection_prompt,
    build_target_file_detection_prompt,
    build_validation_prompt
)
from ._validation import check_id_conflict
from ._exceptions import RuleNotFoundError, RuleConflictError


# Type alias for LLM callable
LLMCallable = Callable[[str], str]


@dataclass
class ConfigUpdateResult:
    """
    Result of a configuration update operation.
    
    Attributes:
        success: Whether the update was successful
        config_type: Type of configuration ("rule", "code_set", "transaction_rule")
        target_file: Path to the file that was (or would be) updated
        generated_yaml: The YAML that was generated
        validation_errors: List of validation errors (empty if valid)
        metadata: Additional metadata about the operation
        backup_path: Path to backup file (if created)
    """
    success: bool
    config_type: str
    target_file: str
    generated_yaml: str
    validation_errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    backup_path: Optional[str] = None
    
    def __str__(self) -> str:
        if self.success:
            return f"✅ Successfully added {self.config_type} to {self.target_file}"
        else:
            errors = "\n".join(f"  - {err}" for err in self.validation_errors)
            return f"❌ Failed to add {self.config_type}:\n{errors}"


class LLMConfigUpdater:
    """
    LLM-powered configuration updater.
    
    Translates natural language requests into properly formatted YAML configuration
    and safely updates the appropriate configuration files.
    
    Example:
        from validedi.llm import LLMConfigUpdater
        
        # Initialize with your LLM
        updater = LLMConfigUpdater(llm=your_llm_callable)
        
        # Add a custom rule
        result = updater.add_custom_config(
            context=\"\"\"
            Add a validation rule that checks if the claim amount in CLM02 
            exceeds $50,000. If it does, flag it as a warning that requires 
            manual review. The rule ID should be CLM-AMOUNT-001.
            \"\"\",
            config_type="rule"
        )
        
        if result.success:
            print(f"✅ Added to {result.target_file}")
        else:
            print(f"❌ Errors: {result.validation_errors}")
    """
    
    def __init__(
        self,
        llm: LLMCallable,
        config_dir: Optional[Path] = None,
        create_backups: bool = True,
        dry_run: bool = False
    ):
        """
        Initialize the config updater.
        
        Args:
            llm: Callable that takes a prompt string and returns a response string
            config_dir: Path to config directory (defaults to validedi/config)
            create_backups: Whether to create backup files before modifying
            dry_run: If True, validate but don't actually write files
        """
        if llm is None:
            raise ValueError("LLM callable is required for LLMConfigUpdater")
        
        self.llm = llm
        self.create_backups = create_backups
        self.dry_run = dry_run
        
        # Determine config directory
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Default to validedi/config
            self.config_dir = Path(__file__).parent.parent / 'config'
        
        if not self.config_dir.exists():
            raise ValueError(f"Config directory not found: {self.config_dir}")
        
        self.rules_dir = self.config_dir / 'rules'
        self.code_sets_dir = self.config_dir / 'code_sets'
        self.transactions_dir = self.config_dir / 'transactions'
    
    def add_custom_config(
        self,
        context: str,
        config_type: str = "auto",
        target_file: Optional[str] = None,
        force: bool = False
    ) -> ConfigUpdateResult:
        """
        Add custom configuration based on natural language context.
        
        Args:
            context: Natural language description of what to add
            config_type: Type of config ("rule", "code_set", "transaction_rule", or "auto")
            target_file: Specific file to update (auto-detected if None)
            force: Skip some validation checks (use with caution)
            
        Returns:
            ConfigUpdateResult with operation details
        """
        try:
            # Step 1: Detect config type if auto
            if config_type == "auto":
                config_type = self._detect_config_type(context)
                if not config_type:
                    return ConfigUpdateResult(
                        success=False,
                        config_type="unknown",
                        target_file="",
                        generated_yaml="",
                        validation_errors=["Could not determine configuration type from context"]
                    )
            
            # Validate config type
            if config_type not in ("rule", "code_set", "transaction_rule"):
                return ConfigUpdateResult(
                    success=False,
                    config_type=config_type,
                    target_file="",
                    generated_yaml="",
                    validation_errors=[f"Invalid config_type: {config_type}. Must be 'rule', 'code_set', or 'transaction_rule'"]
                )
            
            # Step 2: Detect target file if not specified
            if not target_file:
                target_file = self._detect_target_file(context, config_type)
                if not target_file:
                    return ConfigUpdateResult(
                        success=False,
                        config_type=config_type,
                        target_file="",
                        generated_yaml="",
                        validation_errors=["Could not determine target file"]
                    )
            
            # Handle new file creation
            is_new_file = target_file.startswith("NEW:")
            if is_new_file:
                target_file = target_file[4:]  # Remove "NEW:" prefix
            
            # Determine full path
            if config_type == "rule":
                target_path = self.rules_dir / target_file
            elif config_type == "code_set":
                target_path = self.code_sets_dir / target_file
            else:  # transaction_rule
                target_path = self.transactions_dir / target_file
            
            # Step 3: Load existing file content (if exists)
            existing_content = ""
            existing_ids = []
            
            if target_path.exists() and not is_new_file:
                with open(target_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                existing_ids = self._extract_existing_ids(existing_content, config_type)
            
            # Step 4: Generate YAML configuration
            generated_yaml = self._generate_config_yaml(
                context=context,
                config_type=config_type,
                existing_content=existing_content
            )
            
            if not generated_yaml:
                return ConfigUpdateResult(
                    success=False,
                    config_type=config_type,
                    target_file=str(target_path),
                    generated_yaml="",
                    validation_errors=["LLM failed to generate valid YAML"]
                )
            
            # Step 5: Validate generated YAML
            validation_errors = self._validate_generated_yaml(
                generated_yaml=generated_yaml,
                config_type=config_type,
                existing_ids=existing_ids,
                force=force
            )
            
            if validation_errors:
                return ConfigUpdateResult(
                    success=False,
                    config_type=config_type,
                    target_file=str(target_path),
                    generated_yaml=generated_yaml,
                    validation_errors=validation_errors
                )
            
            # Step 6: Create backup if needed
            backup_path = None
            if self.create_backups and target_path.exists() and not self.dry_run:
                backup_path = self._create_backup(target_path)
            
            # Step 7: Update the file
            if not self.dry_run:
                self._update_config_file(
                    target_path=target_path,
                    generated_yaml=generated_yaml,
                    config_type=config_type,
                    is_new_file=is_new_file
                )
            
            # Step 8: Invalidate config cache
            if not self.dry_run:
                try:
                    from validedi.engine.config_loader import invalidate_cache
                    invalidate_cache()
                except:
                    pass  # Cache invalidation is optional
            
            return ConfigUpdateResult(
                success=True,
                config_type=config_type,
                target_file=str(target_path),
                generated_yaml=generated_yaml,
                validation_errors=[],
                metadata={
                    "is_new_file": is_new_file,
                    "dry_run": self.dry_run,
                    "timestamp": datetime.now().isoformat()
                },
                backup_path=backup_path
            )
        
        except Exception as e:
            return ConfigUpdateResult(
                success=False,
                config_type=config_type if 'config_type' in locals() else "unknown",
                target_file=str(target_path) if 'target_path' in locals() else "",
                generated_yaml=generated_yaml if 'generated_yaml' in locals() else "",
                validation_errors=[f"Unexpected error: {str(e)}"],
                metadata={"exception": type(e).__name__}
            )
    
    def preview_config(
        self,
        context: str,
        config_type: str = "auto"
    ) -> str:
        """
        Preview what YAML would be generated without writing to files.
        
        Args:
            context: Natural language description
            config_type: Type of config or "auto"
            
        Returns:
            Generated YAML string
        """
        # Temporarily set dry_run
        original_dry_run = self.dry_run
        self.dry_run = True
        
        try:
            result = self.add_custom_config(context, config_type)
            return result.generated_yaml
        finally:
            self.dry_run = original_dry_run
    
    def get(
        self,
        rule_id: Optional[str] = None,
        config_type: str = "rule",
        filters: Optional[dict] = None
    ):
        """
        Get custom configuration(s) by ID or filters.
        
        Args:
            rule_id: Specific rule/code_set ID to retrieve (if None, return all)
            config_type: Type of config ("rule" or "code_set")
            filters: Optional filters to apply (e.g., {"severity": "error"})
            
        Returns:
            List of ReadResult objects
            
        Example:
            # Get a specific rule
            result = updater.get(rule_id="CLM-001")
            
            # Get all error-severity rules
            results = updater.get(filters={"severity": "error"})
        """
        from .read import get_custom_config
        return get_custom_config(
            rule_id=rule_id,
            config_type=config_type,
            filters=filters,
            config_dir=self.config_dir
        )
    
    def list(
        self,
        config_type: str = "rule",
        filters: Optional[dict] = None
    ):
        """
        List all rule/code_set IDs and their source files.
        
        Args:
            config_type: Type of config ("rule" or "code_set")
            filters: Optional filters to apply
            
        Returns:
            List of (rule_id, source_file) tuples
            
        Example:
            ids = updater.list()
            for rule_id, source_file in ids:
                print(f"{rule_id} -> {source_file}")
        """
        results = self.get(config_type=config_type, filters=filters)
        return [(r.rule_id, r.source_file) for r in results]
    
    def update(
        self,
        rule_id: str,
        context: str,
        config_type: str = "rule"
    ):
        """
        Update an existing custom configuration using natural language.
        
        Args:
            rule_id: The ID of the rule/code_set to update
            context: Natural language description of the changes
            config_type: Type of config ("rule" or "code_set")
            
        Returns:
            UpdateResult with operation details
            
        Example:
            result = updater.update(
                rule_id="CLM-001",
                context="Change severity to warning"
            )
        """
        from .update import update_custom_config
        return update_custom_config(
            rule_id=rule_id,
            context=context,
            llm=self.llm,
            config_type=config_type,
            dry_run=self.dry_run,
            create_backups=self.create_backups,
            config_dir=self.config_dir
        )
    
    def delete(
        self,
        rule_id: str,
        config_type: str = "rule"
    ):
        """
        Delete an existing custom configuration.
        
        Args:
            rule_id: The ID of the rule/code_set to delete
            config_type: Type of config ("rule" or "code_set")
            
        Returns:
            DeleteResult with operation details
            
        Example:
            result = updater.delete(rule_id="CLM-001")
        """
        from .delete import delete_custom_config
        return delete_custom_config(
            rule_id=rule_id,
            config_type=config_type,
            dry_run=self.dry_run,
            create_backups=self.create_backups,
            config_dir=self.config_dir
        )
    
    def _detect_config_type(self, context: str) -> Optional[str]:
        """Detect configuration type from context using LLM."""
        try:
            prompt = build_config_type_detection_prompt(context)
            response = self.llm(prompt).strip().lower()
            
            # Extract config type from response
            if "rule" in response and "transaction" not in response:
                return "rule"
            elif "code_set" in response or "code set" in response:
                return "code_set"
            elif "transaction" in response:
                return "transaction_rule"
            
            # Default to rule if unclear
            return "rule"
        except Exception:
            return None
    
    def _detect_target_file(self, context: str, config_type: str) -> Optional[str]:
        """Detect target file from context using LLM."""
        try:
            # Get list of available files
            if config_type == "rule":
                available_files = [f.name for f in self.rules_dir.glob('*.yaml')]
            elif config_type == "code_set":
                available_files = [f.name for f in self.code_sets_dir.glob('*.yaml')]
            else:
                available_files = [f.name for f in self.transactions_dir.glob('*.yaml')]
            
            if not available_files:
                # Default files
                if config_type == "rule":
                    return "rules_core.yaml"
                elif config_type == "code_set":
                    return "NEW:custom_codes.yaml"
                else:
                    return "NEW:custom_transaction.yaml"
            
            prompt = build_target_file_detection_prompt(context, config_type, available_files)
            response = self.llm(prompt).strip()
            
            # Extract filename from response
            # Look for .yaml filename
            match = re.search(r'(NEW:)?[\w_-]+\.yaml', response)
            if match:
                return match.group(0)
            
            # Default to first available file or create new
            return available_files[0] if available_files else f"NEW:custom_{config_type}.yaml"
        except Exception:
            return None
    
    def _generate_config_yaml(
        self,
        context: str,
        config_type: str,
        existing_content: str
    ) -> str:
        """Generate YAML configuration using LLM."""
        try:
            # Extract examples from existing content
            existing_examples = self._extract_examples(existing_content, config_type)
            
            # Build prompt
            prompt = build_config_generation_prompt(
                context=context,
                config_type=config_type,
                existing_examples=existing_examples
            )
            
            # Get LLM response
            response = self.llm(prompt).strip()
            
            # Clean up response (remove markdown code blocks if present)
            response = self._clean_llm_response(response)
            
            return response
        except Exception as e:
            return ""
    
    def _validate_generated_yaml(
        self,
        generated_yaml: str,
        config_type: str,
        existing_ids: list[str],
        force: bool = False
    ) -> list[str]:
        """
        Validate generated YAML configuration.
        
        Returns list of validation errors (empty if valid).
        """
        errors = []
        
        # 1. Check if YAML is parseable
        try:
            parsed = yaml.safe_load(generated_yaml)
        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML syntax: {str(e)}")
            return errors  # Can't continue validation if YAML is invalid
        
        # 2. Validate structure based on config type
        if config_type == "rule":
            errors.extend(self._validate_rule_structure(parsed, existing_ids))
        elif config_type == "code_set":
            errors.extend(self._validate_code_set_structure(parsed, existing_ids))
        elif config_type == "transaction_rule":
            errors.extend(self._validate_transaction_rule_structure(parsed, existing_ids))
        
        # 3. Use LLM for additional validation (if no critical errors)
        if not errors and not force:
            llm_validation = self._llm_validate(generated_yaml, config_type, existing_ids)
            if llm_validation and not llm_validation.startswith("VALID"):
                errors.append(llm_validation)
        
        return errors
    
    def _validate_rule_structure(self, parsed: Any, existing_ids: list[str]) -> list[str]:
        """Validate rule structure with global ID uniqueness check."""
        errors = []
        
        # Handle different YAML structures
        if isinstance(parsed, dict):
            # Could be a single rule dict or a dict with 'rules' key
            if 'rules' in parsed:
                rules = parsed['rules']
            else:
                rules = [parsed]
        elif isinstance(parsed, list):
            rules = parsed
        else:
            errors.append(f"Invalid rule structure: expected dict or list, got {type(parsed).__name__}")
            return errors
        
        for rule in rules:
            if not isinstance(rule, dict):
                errors.append(f"Rule must be a dictionary, got {type(rule).__name__}")
                continue
            
            # Required fields
            if 'id' not in rule:
                errors.append("Rule missing required field: 'id'")
            else:
                # Global ID uniqueness check across ALL rule files
                conflict = check_id_conflict(
                    rule_id=rule['id'],
                    config_type='rule',
                    rules_dir=self.rules_dir,
                    code_sets_dir=self.code_sets_dir
                )
                if conflict:
                    errors.append(conflict)
            
            if 'type' not in rule:
                errors.append("Rule missing required field: 'type'")
            elif rule['type'] not in (
                'required_segment', 'element_count', 'code_set', 'regex',
                'control_number_match', 'segment_count', 'paired_segments',
                'builtin', 'numeric_validation', 'expression', 'composite_code_set'
            ):
                errors.append(f"Invalid rule type: '{rule['type']}'")
            
            if 'severity' not in rule:
                errors.append("Rule missing required field: 'severity'")
            elif rule['severity'] not in ('error', 'warning', 'info'):
                errors.append(f"Invalid severity: '{rule['severity']}'. Must be 'error', 'warning', or 'info'")
            
            if 'message' not in rule:
                errors.append("Rule missing required field: 'message'")
            
            # Type-specific validation
            if rule.get('type') == 'regex' and 'pattern' not in rule:
                errors.append("Regex rule missing 'pattern' field")
            
            if rule.get('type') == 'code_set' and 'allowed_values' not in rule and 'code_set_id' not in rule:
                errors.append("Code set rule missing 'allowed_values' or 'code_set_id' field")
        
        return errors
    
    def _validate_code_set_structure(self, parsed: Any, existing_ids: list[str]) -> list[str]:
        """Validate code set structure with global ID uniqueness check."""
        errors = []
        
        # Handle string responses (like "code_set" from detection)
        if isinstance(parsed, str):
            errors.append(f"Expected YAML structure, got plain string: '{parsed}'")
            return errors
        
        if not isinstance(parsed, dict):
            errors.append(f"Code set must be a dictionary, got {type(parsed).__name__}")
            return errors
        
        # Required fields
        if 'code_set_id' not in parsed:
            errors.append("Code set missing required field: 'code_set_id'")
        else:
            # Global ID uniqueness check across ALL code set files
            conflict = check_id_conflict(
                rule_id=parsed['code_set_id'],
                config_type='code_set',
                rules_dir=self.rules_dir,
                code_sets_dir=self.code_sets_dir
            )
            if conflict:
                errors.append(conflict)
        
        if 'description' not in parsed:
            errors.append("Code set missing required field: 'description'")
        
        if 'codes' not in parsed:
            errors.append("Code set missing required field: 'codes'")
        elif not isinstance(parsed['codes'], (list, dict)):
            errors.append("'codes' field must be a list or dictionary")
        
        return errors
    
    def _validate_transaction_rule_structure(self, parsed: Any, existing_ids: list[str]) -> list[str]:
        """Validate transaction rule structure."""
        errors = []
        
        # Check if it's a single loop or list of loops
        loops = parsed if isinstance(parsed, list) else [parsed]
        
        for loop in loops:
            if not isinstance(loop, dict):
                errors.append("Loop must be a dictionary")
                continue
            
            # Required fields
            if 'id' not in loop:
                errors.append("Loop missing required field: 'id'")
            elif loop['id'] in existing_ids:
                errors.append(f"Loop ID '{loop['id']}' already exists")
            
            if 'trigger_segment' not in loop:
                errors.append("Loop missing required field: 'trigger_segment'")
            
            if 'required_segments' in loop and not isinstance(loop['required_segments'], list):
                errors.append("'required_segments' must be a list")
        
        return errors
    
    def _llm_validate(self, generated_yaml: str, config_type: str, existing_ids: list[str]) -> str:
        """Use LLM for additional validation."""
        try:
            prompt = build_validation_prompt(generated_yaml, config_type, existing_ids)
            response = self.llm(prompt).strip()
            return response
        except Exception:
            return "VALID"  # Don't fail on LLM validation errors
    
    def _extract_existing_ids(self, content: str, config_type: str) -> list[str]:
        """Extract existing IDs from file content."""
        ids = []
        
        try:
            parsed = yaml.safe_load(content)
            
            if config_type == "rule":
                if isinstance(parsed, dict) and 'rules' in parsed:
                    for rule in parsed['rules']:
                        if 'id' in rule:
                            ids.append(rule['id'])
            elif config_type == "code_set":
                if isinstance(parsed, dict) and 'code_set_id' in parsed:
                    ids.append(parsed['code_set_id'])
            elif config_type == "transaction_rule":
                if isinstance(parsed, dict) and 'loops' in parsed:
                    for loop in parsed['loops']:
                        if 'id' in loop:
                            ids.append(loop['id'])
        except:
            pass
        
        return ids
    
    def _extract_examples(self, content: str, config_type: str) -> dict[str, str]:
        """Extract example configurations from existing content."""
        examples = {}
        
        if not content:
            return examples
        
        try:
            parsed = yaml.safe_load(content)
            
            if config_type == "rule" and isinstance(parsed, dict) and 'rules' in parsed:
                rules = parsed['rules']
                for rule in rules[:3]:  # Get first 3 examples
                    rule_type = rule.get('type', 'unknown')
                    if f'rule_{rule_type}' not in examples:
                        examples[f'rule_{rule_type}'] = yaml.dump([rule], default_flow_style=False)
            
            elif config_type == "code_set":
                # Use the entire code set as example
                examples['code_set_example'] = content[:500]  # First 500 chars
        except:
            pass
        
        return examples
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean LLM response to extract pure YAML."""
        # Remove markdown code blocks
        response = re.sub(r'```ya?ml\s*\n', '', response)
        response = re.sub(r'```\s*$', '', response)
        response = response.strip()
        
        # Remove any leading explanatory text before the YAML
        lines = response.split('\n')
        yaml_start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('-', 'code_set_id:', 'id:')):
                yaml_start = i
                break
        
        return '\n'.join(lines[yaml_start:])
    
    def _create_backup(self, target_path: Path) -> str:
        """Create a backup of the target file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = target_path.parent / f"{target_path.stem}_backup_{timestamp}{target_path.suffix}"
        shutil.copy2(target_path, backup_path)
        return str(backup_path)
    
    def _update_config_file(
        self,
        target_path: Path,
        generated_yaml: str,
        config_type: str,
        is_new_file: bool
    ) -> None:
        """Update the configuration file with generated YAML."""
        if is_new_file:
            # Create new file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(generated_yaml)
        else:
            # For rules, we need to append to the rules: list
            if config_type == "rule":
                # Parse the generated YAML to ensure it's valid
                parsed = yaml.safe_load(generated_yaml)
                
                # Read existing file
                with open(target_path, 'r', encoding='utf-8') as f:
                    existing_data = yaml.safe_load(f)
                
                # Append the new rule(s) to the rules list
                if isinstance(parsed, list):
                    # Generated YAML is a list of rules
                    existing_data['rules'].extend(parsed)
                elif isinstance(parsed, dict):
                    # Generated YAML is a single rule
                    existing_data['rules'].append(parsed)
                
                # Write back the entire file
                with open(target_path, 'w', encoding='utf-8') as f:
                    yaml.dump(existing_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            else:
                # For code sets and other types, append as-is
                with open(target_path, 'a', encoding='utf-8') as f:
                    f.write('\n')  # Ensure newline before appending
                    f.write(generated_yaml)
                    f.write('\n')  # Ensure newline at end


# ── Convenience function ──────────────────────────────────────────────────────

def add_custom_config(
    context: str,
    llm: LLMCallable,
    config_type: str = "auto",
    target_file: Optional[str] = None,
    dry_run: bool = False
) -> ConfigUpdateResult:
    """
    Add custom configuration using natural language.
    
    Convenience function that creates an LLMConfigUpdater and adds config.
    
    Args:
        context: Natural language description of what to add
        llm: LLM callable
        config_type: Type of config ("rule", "code_set", "transaction_rule", or "auto")
        target_file: Specific file to update (auto-detected if None)
        dry_run: If True, validate but don't write files
        
    Returns:
        ConfigUpdateResult with operation details
        
    Example:
        from validedi.llm import add_custom_config
        
        result = add_custom_config(
            context="Add a rule to check that NPI numbers are exactly 10 digits",
            llm=your_llm_callable,
            config_type="rule"
        )
        
        if result.success:
            print(f"✅ Added to {result.target_file}")
        else:
            print(f"❌ Errors: {result.validation_errors}")
    """
    updater = LLMConfigUpdater(llm=llm, dry_run=dry_run)
    return updater.add_custom_config(context, config_type, target_file)
