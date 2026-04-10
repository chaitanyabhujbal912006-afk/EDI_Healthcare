# LLM-Powered Configuration Updater

## Overview

The LLM Config Updater allows administrators to add custom validation rules and code sets using natural language instead of manually writing YAML. This feature uses an LLM to translate human intent into properly formatted configuration files.

## Why This Feature?

**Problem**: Writing YAML configuration requires:
- Understanding the exact YAML structure
- Knowing all required and optional fields
- Proper indentation and syntax
- Awareness of existing IDs to avoid conflicts

**Solution**: Describe what you want in plain English, and the LLM generates the proper YAML configuration automatically.

## Key Features

✅ **Natural Language Input** - Describe rules in plain English  
✅ **Auto-Detection** - Automatically determines config type and target file  
✅ **Validation** - Multiple layers of validation before applying changes  
✅ **Safety** - Dry-run mode, backups, and rollback support  
✅ **LLM-Agnostic** - Works with any LLM provider (OpenAI, Groq, Anthropic, etc.)

## Quick Start

### Installation

```bash
pip install validedi

# Install your preferred LLM provider
pip install openai  # or groq, anthropic, etc.
```

### Basic Usage

```python
from validedi.llm import add_custom_config

# Setup your LLM (example with Groq)
from groq import Groq
client = Groq(api_key="your-api-key")

def llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

# Add a custom rule using natural language
result = add_custom_config(
    context="""
    Add a validation rule that checks if the claim amount in CLM02 
    exceeds $50,000. If it does, flag it as a warning that requires 
    manual review. The rule ID should be CLM-AMOUNT-HIGH.
    """,
    llm=llm,
    config_type="rule"  # or "auto" to let LLM decide
)

if result.success:
    print(f"✅ Added to {result.target_file}")
    print(result.generated_yaml)
else:
    print(f"❌ Errors: {result.validation_errors}")
```

## Configuration Types

### 1. Validation Rules (`config_type="rule"`)

Add custom validation rules for EDI data.

**Example:**
```python
result = add_custom_config(
    context="""
    Add a rule to validate that NPI numbers are exactly 10 digits.
    Rule ID: CUSTOM-NPI-001
    Severity: error
    Message: "NPI must be exactly 10 digits"
    """,
    llm=llm,
    config_type="rule"
)
```

**Generated YAML:**
```yaml
- id: 'CUSTOM-NPI-001'
  type: 'regex'
  target: 'NM109'
  pattern: '^[0-9]{10}$'
  severity: 'error'
  message: 'NPI must be exactly 10 digits'
```

### 2. Code Sets (`config_type="code_set"`)

Add custom code sets for validation.

**Example:**
```python
result = add_custom_config(
    context="""
    Create a code set for internal provider specialty codes:
    - CARD: Cardiology
    - DERM: Dermatology
    - ENDO: Endocrinology
    - NEUR: Neurology
    
    Code set ID: internal_provider_specialties
    """,
    llm=llm,
    config_type="code_set"
)
```

**Generated YAML:**
```yaml
code_set_id: 'internal_provider_specialties'
description: 'Internal provider specialty codes'
codes:
  'CARD': 'Cardiology'
  'DERM': 'Dermatology'
  'ENDO': 'Endocrinology'
  'NEUR': 'Neurology'
```

### 3. Auto-Detection (`config_type="auto"`)

Let the LLM automatically determine the configuration type.

**Example:**
```python
# Will auto-detect as "rule"
result = add_custom_config(
    context="Make sure all claim amounts are positive numbers",
    llm=llm,
    config_type="auto"
)

# Will auto-detect as "code_set"
result = add_custom_config(
    context="Create a list of valid state codes: CA, OR, WA, NV",
    llm=llm,
    config_type="auto"
)
```

## Advanced Usage

### Using the LLMConfigUpdater Class

For more control, use the `LLMConfigUpdater` class directly:

```python
from validedi.llm import LLMConfigUpdater

updater = LLMConfigUpdater(
    llm=llm,
    create_backups=True,  # Create backups before modifying files
    dry_run=False  # Set to True to preview without applying
)

result = updater.add_custom_config(
    context="Add a rule to check ISA segment format",
    config_type="rule",
    target_file="rules_core.yaml",  # Specify target file
    force=False  # Skip some validation checks if True
)
```

### Preview Before Applying

Preview the generated configuration without modifying files:

```python
updater = LLMConfigUpdater(llm=llm)

preview = updater.preview_config(
    context="Add a rule to validate patient date of birth",
    config_type="rule"
)

print("Preview:")
print(preview)

# Review the preview, then apply if satisfied
result = updater.add_custom_config(
    context="Add a rule to validate patient date of birth",
    config_type="rule"
)
```

### Dry Run Mode

Test the entire workflow without modifying files:

```python
updater = LLMConfigUpdater(llm=llm, dry_run=True)

result = updater.add_custom_config(
    context="Add a custom rule",
    config_type="rule"
)

# Files are not modified, but you can see what would happen
print(f"Would add to: {result.target_file}")
print(f"Generated YAML:\n{result.generated_yaml}")
```

### Specify Target File

Explicitly specify which file to update:

```python
result = add_custom_config(
    context="Add adjustment reason code 999: Custom adjustment",
    llm=llm,
    config_type="code_set",
    target_file="adjustment_reason_codes.yaml"
)
```

### Create New Files

Create a new configuration file:

```python
result = add_custom_config(
    context="""
    Create a new code set for our organization's internal codes:
    - INT001: Internal code 1
    - INT002: Internal code 2
    
    Code set ID: organization_internal_codes
    """,
    llm=llm,
    config_type="code_set",
    target_file="NEW:organization_codes.yaml"
)
```

## Validation Layers

The config updater includes multiple validation layers:

### 1. YAML Syntax Validation
- Ensures generated YAML is parseable
- Checks indentation and structure

### 2. Schema Validation
- Verifies all required fields are present
- Validates field types and values
- Checks severity levels (error, warning, info)
- Validates rule types

### 3. ID Conflict Detection
- Checks for duplicate IDs
- Prevents overwriting existing configurations

### 4. LLM Validation
- Uses the LLM to double-check the generated configuration
- Provides additional quality assurance

### 5. Type-Specific Validation

**For Rules:**
- Required fields: id, type, severity, message
- Valid rule types: required_segment, regex, code_set, etc.
- Valid severity levels: error, warning, info
- Type-specific requirements (e.g., regex rules need pattern)

**For Code Sets:**
- Required fields: code_set_id, description, codes
- Proper format (list or dict)
- Unique code_set_id

## Safety Features

### Automatic Backups

Backups are created automatically before modifying files:

```python
updater = LLMConfigUpdater(llm=llm, create_backups=True)

result = updater.add_custom_config(...)

if result.backup_path:
    print(f"Backup created at: {result.backup_path}")
```

Backup files are named: `{filename}_backup_{timestamp}.yaml`

### Dry Run Mode

Test without modifying files:

```python
updater = LLMConfigUpdater(llm=llm, dry_run=True)
result = updater.add_custom_config(...)
# No files are modified
```

### Config Cache Invalidation

The configuration cache is automatically invalidated after updates:

```python
result = updater.add_custom_config(...)
# Config cache is automatically cleared
# Next validation will use the new configuration
```

## Error Handling

The updater provides detailed error information:

```python
result = add_custom_config(
    context="Invalid request",
    llm=llm
)

if not result.success:
    print("Validation Errors:")
    for error in result.validation_errors:
        print(f"  - {error}")
    
    print(f"\nGenerated YAML (for debugging):")
    print(result.generated_yaml)
```

## Best Practices

### 1. Be Specific in Context

❌ **Bad:**
```python
context = "Add a rule for claims"
```

✅ **Good:**
```python
context = """
Add a validation rule that checks if claim amounts in CLM02 exceed $50,000.
If they do, flag as a warning requiring manual review.
Rule ID: CLM-AMOUNT-HIGH
Severity: warning
Message: "Claim amount exceeds $50,000 - manual review required"
"""
```

### 2. Always Review Generated YAML

```python
result = updater.preview_config(context, config_type="rule")
print(result)
# Review carefully before applying
```

### 3. Use Dry Run for Testing

```python
# Test first
updater = LLMConfigUpdater(llm=llm, dry_run=True)
result = updater.add_custom_config(...)

# Apply if satisfied
updater = LLMConfigUpdater(llm=llm, dry_run=False)
result = updater.add_custom_config(...)
```

### 4. Specify Rule IDs

Include the desired rule ID in your context:

```python
context = """
Add a rule to validate NPI format.
Rule ID: ORG-NPI-001
"""
```

### 5. Keep Backups Enabled

```python
updater = LLMConfigUpdater(llm=llm, create_backups=True)
```

### 6. Use Low Temperature for LLM

For consistent configuration generation:

```python
def llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1  # Low temperature for consistency
    )
    return response.choices[0].message.content
```

## Real-World Examples

### Example 1: Organization-Specific Validation

```python
context = """
Our organization requires that all professional claims (837P) with 
place of service code "11" (office) must include a referring provider 
in loop 2310A.

Rule ID: ORG-REFERRING-001
Severity: error
Message: "Office visits require a referring provider - add loop 2310A with referring physician NPI"
"""

result = add_custom_config(context, llm=llm, config_type="rule")
```

### Example 2: Custom Code Set

```python
context = """
Create a code set for our approved facility types:
- HOSP: Hospital
- CLINIC: Outpatient Clinic
- ER: Emergency Room
- URGENT: Urgent Care
- TELE: Telemedicine

Code set ID: approved_facility_types
Description: Organization-approved facility types for claims
"""

result = add_custom_config(context, llm=llm, config_type="code_set")
```

### Example 3: Multiple Related Rules

```python
context = """
Add validation rules for timely filing requirements:

1. Check that claim submission date is not more than 90 days after service date
   Rule ID: TIMELY-FILING-001
   Severity: error
   Message: "Claim submitted more than 90 days after service date"

2. Warn if claim is submitted within 5 days of the 90-day deadline
   Rule ID: TIMELY-FILING-002
   Severity: warning
   Message: "Claim approaching timely filing deadline"
"""

result = add_custom_config(context, llm=llm, config_type="rule")
```

## Troubleshooting

### Issue: LLM generates invalid YAML

**Solution:** Use a more capable model or provide more specific context:

```python
context = """
Add a validation rule with these exact specifications:
- Rule ID: CUSTOM-001
- Type: regex
- Target: ISA15
- Pattern: ^[TP]$
- Severity: error
- Message: "ISA15 must be T or P"
"""
```

### Issue: Duplicate ID errors

**Solution:** Specify a unique ID in your context:

```python
context = """
Add a rule to check NPI format.
Rule ID: ORG-CUSTOM-NPI-001  # Use organization prefix
"""
```

### Issue: Configuration not taking effect

**Solution:** Ensure cache is invalidated (happens automatically) or restart:

```python
from validedi.engine.config_loader import invalidate_cache
invalidate_cache()
```

## API Reference

### `add_custom_config()`

Convenience function for adding configuration.

```python
def add_custom_config(
    context: str,
    llm: Callable[[str], str],
    config_type: str = "auto",
    target_file: Optional[str] = None,
    dry_run: bool = False
) -> ConfigUpdateResult
```

**Parameters:**
- `context`: Natural language description of what to add
- `llm`: LLM callable that takes prompt and returns response
- `config_type`: "rule", "code_set", "transaction_rule", or "auto"
- `target_file`: Specific file to update (auto-detected if None)
- `dry_run`: If True, validate but don't write files

**Returns:** `ConfigUpdateResult` object

### `LLMConfigUpdater`

Main class for configuration updates.

```python
class LLMConfigUpdater:
    def __init__(
        self,
        llm: Callable[[str], str],
        config_dir: Optional[Path] = None,
        create_backups: bool = True,
        dry_run: bool = False
    )
    
    def add_custom_config(
        self,
        context: str,
        config_type: str = "auto",
        target_file: Optional[str] = None,
        force: bool = False
    ) -> ConfigUpdateResult
    
    def preview_config(
        self,
        context: str,
        config_type: str = "auto"
    ) -> str
```

### `ConfigUpdateResult`

Result object containing operation details.

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

## Security Considerations

1. **Review Generated YAML**: Always review before applying to production
2. **Use Dry Run**: Test in dry run mode first
3. **Keep Backups**: Enable automatic backups
4. **Validate Context**: Ensure user context doesn't contain malicious input
5. **LLM Provider**: Use trusted LLM providers with appropriate security

## Performance

- **LLM Calls**: Typically 2-4 LLM calls per operation
  - Config type detection (if auto)
  - Target file detection (if not specified)
  - YAML generation
  - Validation (optional)

- **Optimization Tips**:
  - Specify `config_type` and `target_file` to reduce LLM calls
  - Use caching for repeated operations
  - Choose faster LLM models (e.g., Groq's Llama)

## Support

For issues or questions:
- GitHub Issues: [validedi/issues](https://github.com/yourusername/validedi/issues)
- Documentation: [validedi.readthedocs.io](https://validedi.readthedocs.io)
- Examples: See `validedi/examples/llm_config_update.py`

## License

Same as validedi package license.
