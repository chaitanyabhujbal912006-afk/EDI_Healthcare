"""
Prompt templates for LLM-powered configuration generation.

These prompts guide the LLM to generate properly formatted YAML configurations
that match the existing validedi structure.
"""

from typing import Any


def build_config_generation_prompt(
    context: str,
    config_type: str,
    existing_examples: dict[str, str]
) -> str:
    """
    Build a prompt for generating YAML configuration from natural language.
    
    Args:
        context: User's natural language description of what to add
        config_type: Type of config ("rule", "code_set", or "auto")
        existing_examples: Dict of example YAML structures for reference
        
    Returns:
        Formatted prompt string for LLM
    """
    
    # Build examples section based on config type
    examples_section = _build_examples_section(config_type, existing_examples)
    
    # Build validation rules section
    validation_section = _build_validation_rules(config_type)
    
    return f"""You are a YAML configuration expert for the validedi EDI validation system.

Your task is to convert the user's natural language request into properly formatted YAML configuration that matches the existing validedi structure EXACTLY.

USER REQUEST:
{context}

CONFIGURATION TYPE: {config_type}

{examples_section}

{validation_section}

CRITICAL REQUIREMENTS:
1. Output ONLY valid YAML - no explanations, no markdown code blocks, no extra text
2. Match the exact structure and indentation of the examples above
3. Use 2-space indentation consistently
4. Include all required fields for the configuration type
5. Generate unique IDs that don't conflict with existing ones
6. Use appropriate severity levels: 'error', 'warning', or 'info'
7. Write clear, actionable messages that explain the issue
8. For regex patterns, use proper escaping and test mentally before outputting
9. For code sets, maintain the same format (list or dict) as existing examples
10. Double-check YAML syntax - missing colons, wrong indentation, or unquoted special characters will break the system

OUTPUT FORMAT:
- For rules: Output the complete rule entry (starting with "- id:")
- For code sets: Output the complete code_set_id and codes section
- For auto-detection: First output a comment line "# CONFIG_TYPE: <type>" then the YAML

Generate the YAML configuration now:"""


def build_config_type_detection_prompt(context: str) -> str:
    """
    Build a prompt to detect what type of configuration the user wants to add.
    
    Args:
        context: User's natural language description
        
    Returns:
        Formatted prompt for config type detection
    """
    return f"""You are analyzing a user request to determine what type of EDI configuration they want to add.

USER REQUEST:
{context}

CONFIGURATION TYPES:
1. "rule" - Validation rules that check EDI data (required segments, regex patterns, code sets, control numbers, etc.)
2. "code_set" - Lists of valid codes (adjustment reason codes, CPT codes, diagnosis codes, state codes, etc.)
3. "transaction_rule" - Transaction-specific validation logic (loop structures, segment sequences, etc.)

DETECTION GUIDELINES:
- If the request mentions "validation", "check", "verify", "must", "required", "format" → likely "rule"
- If the request mentions "codes", "values", "list of", "valid options" → likely "code_set"
- If the request mentions "loop", "transaction structure", "segment order" → likely "transaction_rule"
- If unclear, default to "rule" as it's the most common

OUTPUT FORMAT:
Respond with ONLY ONE WORD - the configuration type: "rule", "code_set", or "transaction_rule"

Your response:"""


def build_target_file_detection_prompt(
    context: str,
    config_type: str,
    available_files: list[str]
) -> str:
    """
    Build a prompt to detect which file should be updated.
    
    Args:
        context: User's natural language description
        config_type: Detected configuration type
        available_files: List of available config files
        
    Returns:
        Formatted prompt for file detection
    """
    files_list = "\n".join(f"- {f}" for f in available_files)
    
    return f"""You are determining which configuration file should be updated based on the user's request.

USER REQUEST:
{context}

CONFIGURATION TYPE: {config_type}

AVAILABLE FILES:
{files_list}

DETECTION GUIDELINES:
- For rules: Usually "rules_core.yaml" unless it's transaction-specific
- For code sets: Match the code set name (e.g., "adjustment codes" → "adjustment_reason_codes.yaml")
- If the user mentions a specific transaction (837P, 835, 834), use transaction-specific files
- If creating a NEW code set, suggest a new filename following the pattern: <name>_codes.yaml or <name>.yaml
- Default to the most general file if uncertain

OUTPUT FORMAT:
Respond with ONLY the filename (e.g., "rules_core.yaml" or "adjustment_reason_codes.yaml")
If creating a new file, prefix with "NEW:" (e.g., "NEW:custom_provider_codes.yaml")

Your response:"""


def build_validation_prompt(
    generated_yaml: str,
    config_type: str,
    existing_ids: list[str]
) -> str:
    """
    Build a prompt to validate generated YAML configuration.
    
    Args:
        generated_yaml: The YAML that was generated
        config_type: Type of configuration
        existing_ids: List of existing IDs to check for conflicts
        
    Returns:
        Formatted prompt for validation
    """
    existing_ids_text = ", ".join(existing_ids[:50]) if existing_ids else "None"
    
    return f"""You are validating YAML configuration for the validedi EDI validation system.

GENERATED YAML:
```yaml
{generated_yaml}
```

CONFIGURATION TYPE: {config_type}

EXISTING IDs IN FILE: {existing_ids_text}

VALIDATION CHECKLIST:
1. ✓ Valid YAML syntax (proper indentation, colons, quotes)
2. ✓ All required fields present for {config_type}
3. ✓ ID is unique (not in existing IDs list)
4. ✓ Severity is one of: error, warning, info
5. ✓ Message is clear and actionable
6. ✓ Regex patterns are valid (if applicable)
7. ✓ Structure matches validedi format exactly
8. ✓ No extra fields that don't belong
9. ✓ Proper data types (strings quoted, numbers unquoted)
10. ✓ Consistent 2-space indentation

OUTPUT FORMAT:
If valid, respond with: "VALID"
If invalid, respond with: "INVALID: <specific issue>"

Your response:"""


def _build_examples_section(config_type: str, existing_examples: dict[str, str]) -> str:
    """Build the examples section of the prompt based on config type."""
    
    if config_type == "rule":
        return f"""EXISTING RULE EXAMPLES (for reference):

{existing_examples.get('rule_required_segment', '''- id: 'ENV-001'
  type: 'required_segment'
  target: 'ISA'
  severity: 'error'
  message: 'ISA (Interchange Control Header) segment is missing'
  suggestion: 'Every X12 EDI file must begin with an ISA segment. Ensure the file starts with ISA*'
''')}

{existing_examples.get('rule_regex', '''- id: 'FORMAT-CCYYMMDD'
  type: 'regex'
  pattern: '^[0-9]{{8}}$'
  severity: 'error'
  message: 'Date must be in CCYYMMDD format, got {{value}}'
''')}

{existing_examples.get('rule_code_set', '''- id: 'ENV-004'
  type: 'code_set'
  target: 'ISA15'
  allowed_values: ['T', 'P']
  severity: 'warning'
  message: 'ISA15 (Test/Production Indicator) value {{value}} is not standard'
  suggestion: 'Use T for test transmissions, P for production'
''')}

{existing_examples.get('rule_builtin', '''- id: 'NPI_LUHN_2010AA'
  type: 'builtin'
  handler: 'luhn_check'
  target: 'NM109'
  loop: '2010AA'
  severity: 'error'
  message: 'NPI {{value}} failed Luhn algorithm check'
''')}

RULE TYPES AVAILABLE:
- required_segment: Check if a segment exists
- element_count: Verify number of elements in a segment
- code_set: Validate against allowed values
- regex: Pattern matching for formats
- control_number_match: Match control numbers between segments
- segment_count: Verify segment counts
- paired_segments: Ensure segments are properly paired
- builtin: Use built-in validation handlers (luhn_check, etc.)
- numeric_validation: Ensure values are numeric
- expression: Custom validation expressions"""
    
    elif config_type == "code_set":
        return f"""EXISTING CODE SET EXAMPLES (for reference):

EXAMPLE 1 - Simple list format:
{existing_examples.get('code_set_list', '''code_set_id: 'cas_group_codes'
description: 'Valid CAS01 claim adjustment group codes'
codes:
  - 'PR'  # Patient Responsibility
  - 'CO'  # Contractual Obligation
  - 'OA'  # Other Adjustment
  - 'PI'  # Payer Initiated Reduction
  - 'CR'  # Correction and Reversal
''')}

EXAMPLE 2 - Dictionary format with descriptions:
{existing_examples.get('code_set_dict', '''code_set_id: 'adjustment_reason_codes'
description: 'Common CAS02 Claim Adjustment Reason Codes (CARC)'
codes:
  '1': 'Deductible Amount'
  '2': 'Coinsurance Amount'
  '3': 'Co-payment Amount'
  '45': 'Charge exceeds fee schedule/maximum allowable'
  '50': 'Non-covered service - not deemed medical necessity'
''')}

CODE SET FORMAT RULES:
- Use list format (with dashes) for simple code lists without descriptions
- Use dict format (key: value) when codes need descriptions
- Always include code_set_id and description
- Use single quotes for string values
- Add inline comments with # for clarity"""
    
    elif config_type == "transaction_rule":
        return """TRANSACTION RULE EXAMPLES:

Transaction rules define loop structures and segment sequences for specific transaction types.
These are more complex and typically defined in transaction-specific YAML files.

EXAMPLE - Loop definition:
```yaml
- id: '2010AA'
  parent_id: '2000A'
  trigger_segment: 'NM1'
  trigger_qualifier:
    NM101: '85'
  required_segments:
    - 'NM1'
    - 'N3'
    - 'N4'
  rules:
    - 'NPI_LUHN_2010AA'
    - 'REQUIRED_NM109_2010AA'
```

LOOP STRUCTURE RULES:
- Each loop has a unique id
- parent_id links to parent loop (null for top-level)
- trigger_segment defines what starts the loop
- trigger_qualifier specifies element values that trigger this loop
- required_segments lists mandatory segments in the loop
- rules lists validation rule IDs to apply"""
    
    else:  # auto
        return """CONFIGURATION EXAMPLES:

The system will auto-detect whether you're adding a rule or code set based on your request.

See the specific examples for rules and code sets above."""


def _build_validation_rules(config_type: str) -> str:
    """Build the validation rules section based on config type."""
    
    if config_type == "rule":
        return """REQUIRED FIELDS FOR RULES:
- id: Unique identifier (use uppercase with dashes, e.g., 'CUSTOM-001')
- type: One of the rule types listed above
- severity: 'error', 'warning', or 'info'
- message: Clear description of the issue (can use {{value}} placeholder)

OPTIONAL FIELDS (depending on type):
- target: Segment or element to validate (e.g., 'ISA', 'ISA15', 'NM109')
- pattern: Regex pattern (for type: regex)
- allowed_values: List of valid values (for type: code_set)
- code_set_id: Reference to a code set (for type: code_set)
- handler: Built-in handler name (for type: builtin)
- loop: Loop ID where rule applies (for loop-specific rules)
- suggestion: Helpful guidance on how to fix the issue
- expected_count: Expected number (for type: element_count)
- segment_pair: List of two segments (for type: paired_segments)
- source/target: For control_number_match type"""
    
    elif config_type == "code_set":
        return """REQUIRED FIELDS FOR CODE SETS:
- code_set_id: Unique identifier (lowercase with underscores, e.g., 'custom_provider_codes')
- description: Clear description of what the code set represents
- codes: Either a list (for simple codes) or dict (for codes with descriptions)

FORMAT GUIDELINES:
- Use snake_case for code_set_id
- Keep descriptions concise but informative
- For dict format, ensure all keys are quoted strings
- For list format, use dashes and optional inline comments"""
    
    elif config_type == "transaction_rule":
        return """REQUIRED FIELDS FOR TRANSACTION RULES:
- id: Loop identifier (e.g., '2010AA', '2300', '2400')
- trigger_segment: Segment that starts this loop
- required_segments: List of mandatory segments

OPTIONAL FIELDS:
- parent_id: Parent loop ID (null for top-level loops)
- trigger_qualifier: Dict of element qualifiers that trigger this loop
- rules: List of rule IDs to apply in this loop"""
    
    else:
        return ""
