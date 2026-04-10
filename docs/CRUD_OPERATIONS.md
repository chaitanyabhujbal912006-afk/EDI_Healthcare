# CRUD Operations for ValidEDI Custom Rules

Complete guide to Create, Read, Update, and Delete operations for ValidEDI custom configurations.

## Overview

ValidEDI now supports full CRUD operations for managing custom rules and code sets:

- **Create**: Add new rules using natural language (LLM-powered)
- **Read**: Retrieve and list existing rules (no LLM required)
- **Update**: Modify existing rules using natural language (LLM-powered)
- **Delete**: Remove rules (no LLM required)

## Installation

```python
from validedi.llm import (
    add_custom_config,      # Create
    get_custom_config,      # Read
    list_rule_ids,          # Read (list)
    update_custom_config,   # Update
    delete_custom_config,   # Delete
    LLMConfigUpdater        # Class-based interface
)
```

## Function-Based Interface

### Create: Add Custom Configuration

```python
from validedi.llm import add_custom_config

def my_llm(prompt: str) -> str:
    # Your LLM implementation
    return response

result = add_custom_config(
    context="Add a rule to check that NPI numbers are exactly 10 digits",
    llm=my_llm,
    config_type="rule",  # or "code_set"
    dry_run=False
)

if result.success:
    print(f"✅ Added to {result.target_file}")
    print(result.generated_yaml)
else:
    print(f"❌ Errors: {result.validation_errors}")
```

### Read: Get Configuration

```python
from validedi.llm import get_custom_config, list_rule_ids

# Get a specific rule by ID
results = get_custom_config(rule_id="CLM-001")
if results:
    rule = results[0]
    print(f"Rule ID: {rule.rule_id}")
    print(f"Source: {rule.source_file}")
    print(f"YAML:\n{rule.raw_yaml}")
    print(f"Parsed: {rule.parsed_dict}")

# Get all rules
all_rules = get_custom_config(config_type="rule")
print(f"Found {len(all_rules)} rules")

# Get rules with filters
error_rules = get_custom_config(
    config_type="rule",
    filters={"severity": "error"}
)

# List all rule IDs
ids = list_rule_ids(config_type="rule")
for rule_id, source_file in ids:
    print(f"{rule_id} -> {source_file}")
```

### Update: Modify Configuration

```python
from validedi.llm import update_custom_config

result = update_custom_config(
    rule_id="CLM-001",
    context="Change the severity to warning and update the message to be more descriptive",
    llm=my_llm,
    config_type="rule",
    dry_run=False,
    create_backups=True
)

if result.success:
    print(f"✅ Updated {result.rule_id}")
    print(f"Old YAML:\n{result.old_yaml}")
    print(f"New YAML:\n{result.new_yaml}")
    if result.backup_path:
        print(f"Backup: {result.backup_path}")
else:
    print(f"❌ Errors: {result.validation_errors}")
```

### Delete: Remove Configuration

```python
from validedi.llm import delete_custom_config

result = delete_custom_config(
    rule_id="CLM-001",
    config_type="rule",
    dry_run=False,
    create_backups=True
)

if result.success:
    print(f"✅ Deleted {result.rule_id}")
    print(f"Deleted YAML:\n{result.deleted_yaml}")
    if result.backup_path:
        print(f"Backup: {result.backup_path}")
else:
    print(f"❌ Errors: {result.validation_errors}")
```

## Class-Based Interface

The `LLMConfigUpdater` class provides a unified interface for all CRUD operations:

```python
from validedi.llm import LLMConfigUpdater

# Initialize updater
updater = LLMConfigUpdater(
    llm=my_llm,
    create_backups=True,
    dry_run=False
)

# Create
result = updater.add_custom_config(
    context="Add a rule for NPI validation",
    config_type="rule"
)

# Read
rule = updater.get(rule_id="CLM-001")
all_rules = updater.get()  # Get all
error_rules = updater.get(filters={"severity": "error"})

# List
ids = updater.list(config_type="rule")

# Update
result = updater.update(
    rule_id="CLM-001",
    context="Change severity to warning"
)

# Delete
result = updater.delete(rule_id="CLM-001")
```

## Features

### Global ID Uniqueness

Rule IDs are now checked globally across ALL YAML files in the rules directory:

```python
# If CLM-001 exists in rules_837.yaml, you cannot create it in rules_core.yaml
result = add_custom_config(
    context="Add rule with ID CLM-001",
    llm=my_llm
)
# Will fail with: "Rule ID 'CLM-001' already exists in rules_837.yaml"
```

### Automatic Backups

Before any write operation (update/delete), a timestamped backup is created:

```
rules_core.yaml
rules_core_backup_20260405_143022.yaml  # Backup created automatically
```

### Cache Invalidation

After any write operation, the configuration cache is automatically invalidated to ensure changes take effect immediately.

### Dry Run Mode

Test operations without modifying files:

```python
# Preview what would be updated
result = update_custom_config(
    rule_id="CLM-001",
    context="Change severity",
    llm=my_llm,
    dry_run=True  # No files modified
)

print(f"Would update:\n{result.new_yaml}")
```

## Error Handling

### RuleNotFoundError

Raised when trying to read, update, or delete a non-existent rule:

```python
from validedi.llm import RuleNotFoundError

try:
    result = update_custom_config(
        rule_id="NONEXISTENT",
        context="Change something",
        llm=my_llm
    )
except RuleNotFoundError as e:
    print(f"Rule not found: {e.rule_id}")
```

### RuleConflictError

Raised when trying to create a rule with an ID that already exists:

```python
from validedi.llm import RuleConflictError

try:
    result = add_custom_config(
        context="Add rule with existing ID",
        llm=my_llm
    )
except RuleConflictError as e:
    print(f"Conflict: {e.rule_id} exists in {e.source_file}")
```

## Result Types

### ConfigUpdateResult (Create)

```python
@dataclass
class ConfigUpdateResult:
    success: bool
    config_type: str
    target_file: str
    generated_yaml: str
    validation_errors: list[str]
    metadata: dict
    backup_path: Optional[str]
```

### ReadResult (Read)

```python
@dataclass
class ReadResult:
    rule_id: str
    source_file: str
    raw_yaml: str
    parsed_dict: dict
    config_type: str
```

### UpdateResult (Update)

```python
@dataclass
class UpdateResult:
    success: bool
    rule_id: str
    old_yaml: str
    new_yaml: str
    source_file: str
    validation_errors: list[str]
    backup_path: Optional[str]
```

### DeleteResult (Delete)

```python
@dataclass
class DeleteResult:
    success: bool
    rule_id: str
    deleted_yaml: str
    source_file: str
    validation_errors: list[str]
    backup_path: Optional[str]
```

## Best Practices

### 1. Use Dry Run for Testing

Always test with `dry_run=True` first:

```python
# Test first
result = update_custom_config(..., dry_run=True)
if result.success:
    # Now do it for real
    result = update_custom_config(..., dry_run=False)
```

### 2. Enable Backups

Always keep backups enabled for safety:

```python
updater = LLMConfigUpdater(
    llm=my_llm,
    create_backups=True  # Recommended
)
```

### 3. Check Results

Always check the `success` flag:

```python
result = update_custom_config(...)
if not result.success:
    print(f"Failed: {result.validation_errors}")
    return
```

### 4. Use Filters for Bulk Operations

When working with multiple rules:

```python
# Get all error-severity rules
error_rules = get_custom_config(filters={"severity": "error"})

# Update them one by one
for rule in error_rules:
    result = update_custom_config(
        rule_id=rule.rule_id,
        context="Change to warning",
        llm=my_llm
    )
```

### 5. List Before Delete

Always verify what you're deleting:

```python
# List all rules first
ids = list_rule_ids()
print("Available rules:")
for rule_id, source_file in ids:
    print(f"  {rule_id} in {source_file}")

# Then delete
result = delete_custom_config(rule_id="CLM-001")
```

## Complete Example

```python
from validedi.llm import LLMConfigUpdater

def my_llm(prompt: str) -> str:
    # Your LLM implementation (OpenAI, Anthropic, etc.)
    return response

# Initialize updater
updater = LLMConfigUpdater(llm=my_llm, create_backups=True)

# 1. Create a new rule
print("Creating new rule...")
result = updater.add_custom_config(
    context="Add a rule to validate that claim amounts are positive numbers",
    config_type="rule"
)
if result.success:
    print(f"✅ Created rule in {result.target_file}")
    rule_id = result.metadata.get('rule_id')  # Extract ID from generated YAML
else:
    print(f"❌ Failed: {result.validation_errors}")
    exit(1)

# 2. Read the rule back
print(f"\nReading rule {rule_id}...")
rules = updater.get(rule_id=rule_id)
if rules:
    print(f"Found: {rules[0].parsed_dict}")

# 3. Update the rule
print(f"\nUpdating rule {rule_id}...")
result = updater.update(
    rule_id=rule_id,
    context="Change severity from error to warning"
)
if result.success:
    print(f"✅ Updated successfully")
    print(f"Backup: {result.backup_path}")
else:
    print(f"❌ Failed: {result.validation_errors}")

# 4. List all rules
print("\nListing all rules...")
ids = updater.list()
print(f"Total rules: {len(ids)}")
for rid, source in ids[:5]:  # Show first 5
    print(f"  {rid} -> {source}")

# 5. Delete the rule
print(f"\nDeleting rule {rule_id}...")
result = updater.delete(rule_id=rule_id)
if result.success:
    print(f"✅ Deleted successfully")
    print(f"Backup: {result.backup_path}")
else:
    print(f"❌ Failed: {result.validation_errors}")
```

## Migration from v0.3.1

If you were using the old `add_custom_config` function, it still works the same way. The new CRUD operations are additions:

```python
# Old way (still works)
from validedi.llm import add_custom_config
result = add_custom_config(context="...", llm=my_llm)

# New way (more options)
from validedi.llm import (
    add_custom_config,      # Same as before
    get_custom_config,      # NEW
    update_custom_config,   # NEW
    delete_custom_config    # NEW
)
```

## Troubleshooting

### "Rule not found" error

Make sure the rule ID exists:

```python
# Check if rule exists first
ids = list_rule_ids()
if ("CLM-001", any_file) not in ids:
    print("Rule CLM-001 does not exist")
```

### "Duplicate ID" error

Check all files for the ID:

```python
# Find where the ID exists
all_rules = get_custom_config()
for rule in all_rules:
    if rule.rule_id == "CLM-001":
        print(f"Found in: {rule.source_file}")
```

### LLM returns invalid YAML

The system validates YAML automatically. If validation fails, check:

1. LLM prompt is clear
2. LLM is following instructions
3. Try with `dry_run=True` to see what's generated

### Cache not invalidating

The system automatically invalidates cache, but you can do it manually:

```python
from validedi.engine.config_loader import invalidate_cache
invalidate_cache()
```

## API Reference

See the docstrings in the source code for complete API documentation:

- `validedi/src/validedi/llm/read.py` - Read operations
- `validedi/src/validedi/llm/update.py` - Update operations
- `validedi/src/validedi/llm/delete.py` - Delete operations
- `validedi/src/validedi/llm/config_updater.py` - Create operations and class interface
