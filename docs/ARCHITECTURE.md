# ValidEDI Architecture Deep Dive

**A comprehensive technical guide to how ValidEDI works internally**

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Configuration System](#configuration-system)
6. [Validation Engine](#validation-engine)
7. [LLM Integration](#llm-integration)
8. [Performance Considerations](#performance-considerations)
9. [Extension Points](#extension-points)
10. [Design Decisions](#design-decisions)

---

## Overview

ValidEDI is built on three core principles:

1. **Configuration-Driven** - Rules and codes in YAML, not hardcoded
2. **Type-Safe** - Full Pydantic v2 models with validation
3. **Extensible** - Easy to add new rules, codes, and transaction types

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Code                            │
│  parse() / validate() / explain() / ask_followup()          │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                     ValidEDI Core                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Detector │  │ Parser   │  │Validator │  │ LLM      │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                  Configuration Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Registry  │  │ Rules    │  │Code Sets │  │ Prompts  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## System Architecture

### Module Structure

```
validedi/
├── src/validedi/
│   ├── __init__.py              # Public API
│   ├── engine/                  # Core parsing and validation
│   │   ├── detector.py          # Transaction type detection
│   │   ├── tokenizer.py         # EDI tokenization
│   │   ├── parser.py            # Main parser
│   │   ├── validator.py         # Main validator
│   │   ├── loop_builder.py      # Hierarchical loop construction
│   │   ├── rule_executor.py     # Rule execution engine
│   │   ├── config_loader.py     # Configuration loading
│   │   └── models.py            # Pydantic models
│   ├── handlers/                # Validation handlers
│   │   ├── npi_luhn.py          # NPI Luhn check
│   │   ├── cross_segment.py     # Cross-segment validation
│   │   └── duplicate_check.py   # Duplicate detection
│   ├── llm/                     # LLM integration
│   │   ├── explainer.py         # Main LLM engine
│   │   ├── prompts.py           # Prompt builders
│   │   └── templates.py         # Rule-based templates
│   ├── config/                  # YAML configurations
│   │   ├── registry.yaml        # Transaction registry
│   │   ├── transactions/        # Transaction definitions
│   │   ├── rules/               # Validation rules
│   │   └── code_sets/           # Code value lists
│   └── utils/                   # Utilities
│       └── exceptions.py        # Custom exceptions
```

---

## Core Components

### 1. Detector (`detector.py`)

**Purpose:** Identify the transaction type from raw EDI content.

**How it works:**

1. Extracts ISA and GS segments
2. Reads ST01 (transaction set identifier)
3. Maps to transaction type (837P, 837I, 835, 834)
4. Determines subtype from additional qualifiers

**Example:**
```python
# ST*837*0001*005010X222A1~
# ST01 = 837, Implementation = 005010X222A1
# Result: 837P (Professional)
```

**Key Methods:**
- `detect_transaction_type(content: str) -> tuple[str, str]`
- `detect_delimiters(content: str) -> tuple[str, str, str]`

---

### 2. Tokenizer (`tokenizer.py`)

**Purpose:** Break raw EDI into segments and elements.

**How it works:**
1. Detects delimiters from ISA segment
2. Splits content by segment terminator (~)
3. Splits segments by element separator (*)
4. Handles component separators (:)
5. Preserves element positions

**Example:**
```python
# Input: "NM1*IL*1*SMITH*JOHN****MI*123456789~"
# Output: Segment(
#   segment_id='NM1',
#   elements=['IL', '1', 'SMITH', 'JOHN', '', '', '', '', 'MI', '123456789']
# )
```

**Key Methods:**
- `tokenize(content: str) -> List[Segment]`
- `split_segments(content: str, terminator: str) -> List[str]`
- `split_elements(segment: str, separator: str) -> List[str]`

---

### 3. Parser (`parser.py`)

**Purpose:** Convert tokenized segments into structured data.

**How it works:**
1. Loads transaction configuration from YAML
2. Builds hierarchical loop structure
3. Extracts envelope metadata
4. Creates ParsedEDI object with type-safe models

**Parsing Pipeline:**
```
Raw EDI → Detect Type → Tokenize → Build Loops → Extract Data → ParsedEDI
```

**Key Methods:**
- `parse(source: str | Path) -> ParsedEDI`
- `_read_source(source) -> str`
- `_is_file_path(source: str) -> bool`

**ParsedEDI Model:**
```python
class ParsedEDI(BaseModel):
    envelope: EnvelopeMeta          # ISA/GS/ST metadata
    loops: List[Loop]               # Hierarchical loops
    segments: List[Segment]         # Flat segment list
    raw_content: str                # Original EDI
    transaction_type: str           # 837P, 837I, 835, 834
    version: str                    # 005010
```

---

### 4. Loop Builder (`loop_builder.py`)

**Purpose:** Organize flat segments into hierarchical loop structure.

**How it works:**
1. Reads loop definitions from transaction YAML
2. Identifies loop triggers (segment + qualifier)
3. Builds parent-child relationships
4. Nests segments within loops

**Loop Hierarchy Example (837P):**
```
Loop 2000A (Billing Provider)
  ├── NM1*85 (Billing Provider Name)
  ├── N3 (Address)
  ├── N4 (City/State/ZIP)
  └── Loop 2000B (Subscriber)
      ├── NM1*IL (Subscriber Name)
      ├── DMG (Demographics)
      └── Loop 2300 (Claim)
          ├── CLM (Claim Information)
          ├── HI (Diagnosis Codes)
          └── Loop 2400 (Service Line)
              ├── LX (Line Number)
              └── SV1 (Service)
```

**Key Methods:**
- `build_loops(segments: List[Segment], config: dict) -> List[Loop]`
- `_find_loop_definition(segment: Segment, configs: List) -> dict`
- `_nest_loops(loops: List[Loop]) -> List[Loop]`

---

### 5. Validator (`validator.py`)

**Purpose:** Execute validation rules and generate results.

**How it works:**
1. Loads validation rules from YAML
2. Executes rules in order
3. Collects errors, warnings, and info messages
4. Generates validation summary

**Validation Pipeline:**
```
ParsedEDI → Load Rules → Execute Rules → Collect Issues → ValidationResult
```

**Key Methods:**
- `validate(source: str | ParsedEDI) -> ValidationResult`
- `_execute_rules(parsed: ParsedEDI, rules: List) -> List[ValidationError]`

**ValidationResult Model:**
```python
class ValidationResult(BaseModel):
    is_valid: bool                  # No errors
    error_count: int                # Critical issues
    warning_count: int              # Non-critical issues
    info_count: int                 # Informational
    errors: List[ValidationError]   # All issues
    summary: str                    # Plain-English summary
```

---

### 6. Rule Executor (`rule_executor.py`)

**Purpose:** Execute individual validation rules.

**Rule Types:**
1. **required_segment** - Segment must exist
2. **required_element** - Element must have value
3. **regex** - Pattern matching
4. **code_set** - Value in allowed list
5. **builtin** - Custom handler function
6. **numeric_validation** - Must be numeric
7. **numeric_range** - Within min/max
8. **control_number_match** - Control numbers match
9. **segment_count** - Correct segment count
10. **date_format** - Date format validation

**Execution Flow:**
```python
for rule in rules:
    if rule['type'] == 'regex':
        execute_regex_rule(rule, segments)
    elif rule['type'] == 'code_set':
        execute_code_set_rule(rule, segments)
    elif rule['type'] == 'builtin':
        execute_builtin_handler(rule, segments)
    # ... etc
```

**Key Methods:**
- `execute_rule(rule: dict, parsed: ParsedEDI) -> List[ValidationError]`
- `execute_regex_rule(rule: dict, segments: List) -> List[ValidationError]`
- `execute_builtin_rule(rule: dict, parsed: ParsedEDI) -> List[ValidationError]`

---

### 7. Config Loader (`config_loader.py`)

**Purpose:** Load and cache YAML configurations.

**How it works:**
1. Locates config files in package
2. Parses YAML with safe loader
3. Caches configurations in memory
4. Thread-safe access with locks

**Configuration Types:**
- **Registry** - Transaction type mappings
- **Transactions** - Loop definitions and structure
- **Rules** - Validation rule definitions
- **Code Sets** - Allowed value lists

**Key Methods:**
- `load_transaction_config(tx_type: str) -> dict`
- `load_rules(tx_type: str) -> List[dict]`
- `load_code_set(code_set_id: str) -> dict`
- `_get_config_path() -> Path`

**Caching Strategy:**
```python
_config_cache = {}
_cache_lock = threading.Lock()

def load_config(path: str) -> dict:
    with _cache_lock:
        if path not in _config_cache:
            _config_cache[path] = yaml.safe_load(open(path))
        return _config_cache[path]
```

---

## Data Flow

### Parse Flow

```
┌─────────────┐
│  Raw EDI    │
│   String    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Detector   │ ─── Identify transaction type (837P, 835, etc.)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Tokenizer   │ ─── Split into segments and elements
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Config Loader│ ─── Load transaction YAML
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Loop Builder │ ─── Build hierarchical structure
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  ParsedEDI  │ ─── Type-safe Pydantic model
└─────────────┘
```

### Validate Flow

```
┌─────────────┐
│ ParsedEDI   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Config Loader│ ─── Load validation rules
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Rule Executor│ ─── Execute each rule
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Handlers   │ ─── Custom validation logic
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ValidationRes│ ─── Collect all issues
└─────────────┘
```

### LLM Explain Flow

```
┌─────────────┐   ┌─────────────┐
│ ParsedEDI   │   │ValidationRes│
└──────┬──────┘   └──────┬──────┘
       │                 │
       └────────┬────────┘
                │
                ▼
        ┌─────────────┐
        │Prompt Builder│ ─── Build explanation prompt
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐
        │  User's LLM │ ─── Call provided LLM function
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐
        │ExplainResult│ ─── Plain-English report
        └─────────────┘
```

---

## Configuration System

### YAML Structure

#### Registry (`registry.yaml`)
```yaml
transactions:
  '837':
    subtypes:
      '005010X222A1': '837p'
      '005010X223A2': '837i'
  '835':
    subtypes:
      '005010X221A1': '835'
  '834':
    subtypes:
      '005010X220A1': '834'
```

#### Transaction Config (`837p.yaml`)
```yaml
transaction_type: '837p'
description: 'Professional Health Care Claim'

loops:
  - id: '2000A'
    parent_id: null
    trigger_segment: 'HL'
    trigger_qualifier:
      element: 3
      value: '20'
    required_segments: ['NM1', 'N3', 'N4']
    rules: ['NPI_LUHN_2010AA']
```

#### Validation Rules (`rules_837.yaml`)
```yaml
rules:
  - id: 'CLM01_REQUIRED'
    type: 'required_element'
    target: 'CLM01'
    severity: 'error'
    message: 'CLM01 (Patient Control Number) is blank'
    suggestion: 'CLM01 must be a unique identifier'
```

#### Code Sets (`entity_codes.yaml`)
```yaml
code_set_id: 'entity_codes'
description: 'NM101 Entity Identifier Codes'
codes:
  '85': 'Billing Provider'
  'IL': 'Insured or Subscriber'
  'PR': 'Payer'
```

---

## Validation Engine

### Rule Execution Order

1. **Envelope Rules** (ISA/GS/ST structure)
2. **Control Number Rules** (matching)
3. **Segment Count Rules** (SE01 validation)
4. **Format Rules** (dates, NPIs, amounts)
5. **Business Rules** (required entities, charge totals)
6. **Code Set Rules** (valid code values)

### Handler System

Handlers are Python functions for complex validation:

```python
# handlers/npi_luhn.py
def validate_npi_luhn(npi: str) -> bool:
    """Validate NPI using Luhn algorithm."""
    if len(npi) != 10 or not npi.isdigit():
        return False
    
    # Luhn algorithm implementation
    total = 0
    for i, digit in enumerate(npi[:-1]):
        n = int(digit)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(npi[-1])
```

**Handler Registration:**
```python
# handlers/__init__.py
HANDLER_REGISTRY = {
    'luhn_check': validate_npi_luhn,
    'charge_total_consistency': validate_charge_total,
    'duplicate_member_check': check_duplicate_members,
}
```

---

## LLM Integration

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User's LLM                           │
│  (OpenAI, Groq, Bedrock, Gemini, Local, Custom)        │
└────────────────────┬────────────────────────────────────┘
                     │ Callable: (str) -> str
                     │
┌────────────────────▼────────────────────────────────────┐
│                 LLMExplainer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │Prompt Builder│  │  LLM Caller  │  │  Templates   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Prompt Engineering

**Explanation Prompt Structure:**
```
You are a healthcare EDI specialist...

TRANSACTION TYPE: 837P
SENDER: ABC123
RECEIVER: XYZ789

KEY DATA:
• Total Claims: 3
• Total Billed: $4,250.00
• Billing Provider: Dr. Smith (NPI: 1234567890)

VALIDATION RESULTS:
⚠️  Warning: CLM06 missing on Claim #2

Write a structured report with:
1. OVERVIEW
2. KEY PARTIES
3. FINANCIAL SUMMARY
4. VALIDATION STATUS
5. ACTION ITEMS
```

**Q&A Prompt Structure:**
```
You are a healthcare EDI expert...

FILE CONTEXT:
• Total Claims: 3
• Total Billed: $4,250.00

VALIDATION: File is valid with 1 warning

USER QUESTION: What is the total billed amount?

Answer concisely in plain English.
```

### Fallback Strategy

```python
def explain(edi_result, val_result, llm=None):
    if llm is None:
        # Use rule-based templates
        return render_template(edi_result, val_result)
    
    try:
        # Try user's LLM
        prompt = build_prompt(edi_result, val_result)
        response = llm(prompt)
        return ExplainResult(response, source="llm")
    except Exception:
        # Fall back to templates
        return render_template(edi_result, val_result)
```

---

## Performance Considerations

### Parsing Performance

**Typical Performance:**
- Small file (10 KB, ~100 segments): ~10ms
- Medium file (100 KB, ~1000 segments): ~50ms
- Large file (1 MB, ~10000 segments): ~500ms

**Optimization Strategies:**
1. **Lazy Loading** - Load configs only when needed
2. **Caching** - Cache parsed configs in memory
3. **Thread Safety** - Use locks for cache access
4. **Efficient Tokenization** - Single-pass parsing

### Validation Performance

**Rule Execution:**
- Simple rules (regex, required): <1ms per rule
- Complex rules (builtin handlers): 1-5ms per rule
- Total validation: 10-50ms for typical file

**Optimization Strategies:**
1. **Early Exit** - Stop on critical errors if needed
2. **Parallel Execution** - Run independent rules in parallel
3. **Rule Ordering** - Fast rules first, slow rules last

### Memory Usage

**Typical Memory:**
- Small file: ~1 MB
- Medium file: ~10 MB
- Large file: ~100 MB

**Memory Optimization:**
1. **Streaming** - Process segments one at a time (future)
2. **Lazy Evaluation** - Build loops on demand
3. **Garbage Collection** - Clear caches periodically

---

## Extension Points

### 1. Add New Transaction Type

**Step 1:** Create transaction config
```yaml
# config/transactions/270.yaml
transaction_type: '270'
description: 'Eligibility Inquiry'
loops:
  - id: '2000A'
    trigger_segment: 'HL'
    # ...
```

**Step 2:** Add to registry
```yaml
# config/registry.yaml
transactions:
  '270':
    subtypes:
      '005010X279A1': '270'
```

**Step 3:** Create validation rules
```yaml
# config/rules/rules_270.yaml
rules:
  - id: 'RULE_001'
    type: 'required_segment'
    # ...
```

### 2. Add Custom Validation Rule

**Step 1:** Create handler
```python
# handlers/my_custom_check.py
def my_custom_validation(parsed: ParsedEDI) -> List[ValidationError]:
    errors = []
    # Your validation logic
    return errors
```

**Step 2:** Register handler
```python
# handlers/__init__.py
HANDLER_REGISTRY['my_custom_check'] = my_custom_validation
```

**Step 3:** Add rule to YAML
```yaml
# config/rules/rules_custom.yaml
rules:
  - id: 'MY_CUSTOM_RULE'
    type: 'builtin'
    handler: 'my_custom_check'
    severity: 'error'
    message: 'Custom validation failed'
```

### 3. Add New Code Set

**Create YAML file:**
```yaml
# config/code_sets/my_codes.yaml
code_set_id: 'my_codes'
description: 'My custom codes'
codes:
  'A': 'Value A'
  'B': 'Value B'
```

**Use in rules:**
```yaml
rules:
  - id: 'MY_CODE_CHECK'
    type: 'code_set'
    target: 'SEGMENT01'
    code_set_id: 'my_codes'
    severity: 'error'
    message: 'Invalid code value'
```

---

## Design Decisions

### 1. Configuration-Driven vs. Hardcoded

**Decision:** Use YAML configuration files

**Rationale:**
- Easy to modify without code changes
- Version control friendly
- Shareable across teams
- Non-developers can update rules

**Trade-offs:**
- Slightly slower than hardcoded (mitigated by caching)
- Requires YAML parsing
- More files to manage

### 2. Pydantic v2 for Models

**Decision:** Use Pydantic v2 for all data models

**Rationale:**
- Type safety and validation
- Automatic serialization/deserialization
- IDE autocomplete support
- Runtime type checking

**Trade-offs:**
- Dependency on Pydantic
- Learning curve for contributors
- Slight performance overhead

### 3. Hierarchical Loop Structure

**Decision:** Build hierarchical loops instead of flat segments

**Rationale:**
- Matches EDI logical structure
- Easier navigation
- Better for complex queries
- More intuitive API

**Trade-offs:**
- More complex parsing
- Higher memory usage
- Slower for simple use cases

### 4. LLM-Agnostic Interface

**Decision:** Accept any callable instead of specific providers

**Rationale:**
- Maximum flexibility
- No vendor lock-in
- Works with future LLMs
- No provider dependencies

**Trade-offs:**
- Users must implement LLM wrapper
- No built-in provider support
- More setup required

### 5. Rule-Based Fallback

**Decision:** Always provide rule-based templates

**Rationale:**
- Works without LLM
- No API costs
- Predictable output
- Good for testing

**Trade-offs:**
- Less natural language
- More verbose code
- Maintenance overhead

---

## Summary

ValidEDI's architecture is designed for:

1. **Flexibility** - Configuration-driven, easy to extend
2. **Type Safety** - Pydantic models throughout
3. **Performance** - Caching, efficient parsing
4. **Maintainability** - Clear separation of concerns
5. **Extensibility** - Multiple extension points

The combination of YAML configuration, type-safe models, and modular design makes ValidEDI both powerful and easy to customize for specific needs.

---

**Next Steps:**
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Custom Validation](CUSTOM_VALIDATION.md) - Add your own rules
- [Configuration Guide](CONFIGURATION.md) - Customize ValidEDI
