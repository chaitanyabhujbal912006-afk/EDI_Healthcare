# ValidEDI - Complete LLM Implementation Guide

**For AI Assistants: This guide provides everything you need to use ValidEDI library proficiently.**

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Core Functions](#core-functions)
3. [Data Models](#data-models)
4. [Common Patterns](#common-patterns)
5. [Error Handling](#error-handling)
6. [Advanced Usage](#advanced-usage)
7. [Configuration](#configuration)

---

## Quick Reference

### Installation
```python
pip install validedi
```

### Essential Imports
```python
from validedi import parse, validate
from validedi.llm import explain, ask_followup, chat
```

### 30-Second Example
```python
# Parse and validate
result = validate('claim.edi')

# Check results
if result.is_valid:
    print("✅ Valid EDI file")
else:
    for error in result.errors:
        print(f"❌ {error.message}")
```

---

## Core Functions

### 1. `parse(source)` - Parse EDI Files

**Purpose**: Convert EDI file into structured Python objects

**Signature**:
```python
def parse(source: str | Path) -> ParsedEDI
```

**Parameters**:
- `source`: File path (str/Path) or raw EDI string

**Returns**: `ParsedEDI` object with:
- `envelope`: Metadata (sender, receiver, transaction type, etc.)
- `loops`: Hierarchical loop structure
- `raw`: Original EDI content

**Usage**:
```python
# From file path
result = parse('claim.edi')

# From string
edi_string = "ISA*00*..."
result = parse(edi_string)

# Access data
print(result.envelope.transaction_type)  # "837P", "835", etc.
print(result.envelope.sender_id)
print(result.envelope.receiver_id)
print(len(result.loops))
```

**When to Use**:
- Need structured access to EDI data
- Want to navigate loops and segments
- Don't need validation (faster)

---

### 2. `validate(source)` - Parse and Validate

**Purpose**: Parse EDI file AND run validation rules

**Signature**:
```python
def validate(source: str | Path) -> ValidationResult
```

**Parameters**:
- `source`: File path (str/Path) or raw EDI string

**Returns**: `ValidationResult` object with:
- `parsed`: The ParsedEDI object
- `errors`: List of validation errors
- `is_valid`: Boolean (True if no errors)
- `error_count`: Number of errors
- `warning_count`: Number of warnings

**Usage**:
```python
# Validate file
result = validate('claim.edi')

# Check validity
if result.is_valid:
    print("✅ Valid")
else:
    print(f"❌ {result.error_count} errors")
    
# Access parsed data
tx_type = result.parsed.envelope.transaction_type

# Iterate errors
for error in result.errors:
    print(f"[{error.severity}] {error.code}: {error.message}")
    print(f"  Location: {error.segment} at position {error.position}")
```

**When to Use**:
- Need to check if EDI is valid
- Want detailed error messages
- Need both parsing and validation

---

### 3. `explain(edi_result, val_result, llm=None)` - Generate Explanations

**Purpose**: Create plain-English explanation of EDI file

**Signature**:
```python
def explain(
    edi_result: ParsedEDI,
    val_result: ValidationResult,
    llm: Callable[[str], str] | None = None,
    force_rule_based: bool = False
) -> ExplanationResult
```

**Parameters**:
- `edi_result`: Result from `parse()`
- `val_result`: Result from `validate()`
- `llm`: Optional LLM function `(prompt: str) -> str`
- `force_rule_based`: Use templates instead of LLM

**Returns**: `ExplanationResult` with:
- `report`: Plain-English explanation
- `used_llm`: Whether LLM was used

**Usage**:

**Without LLM (rule-based templates)**:
```python
edi_result = parse('claim.edi')
val_result = validate(edi_result)

# Generate explanation
result = explain(edi_result, val_result)
print(result.report)
```

**With LLM (OpenAI)**:
```python
from openai import OpenAI

client = OpenAI(api_key="your-key")

def my_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Use LLM
result = explain(edi_result, val_result, llm=my_llm)
print(result.report)
```

**With LLM (Groq - Free)**:
```python
from groq import Groq

client = Groq(api_key="your-key")

def my_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

result = explain(edi_result, val_result, llm=my_llm)
```

**When to Use**:
- Need human-readable explanation
- Want to understand EDI content
- Need to explain errors to non-technical users

---

### 4. `ask_followup(question, edi_result, val_result, llm)` - Ask Questions

**Purpose**: Ask questions about EDI file in plain English

**Signature**:
```python
def ask_followup(
    question: str,
    edi_result: ParsedEDI,
    val_result: ValidationResult,
    llm: Callable[[str], str]
) -> str
```

**Parameters**:
- `question`: Your question in plain English
- `edi_result`: Result from `parse()`
- `val_result`: Result from `validate()`
- `llm`: LLM function (required)

**Returns**: String answer

**Usage**:
```python
# Parse and validate
edi_result = parse('claim.edi')
val_result = validate(edi_result)

# Ask questions
answer = ask_followup(
    "What is the total billed amount?",
    edi_result,
    val_result,
    llm=my_llm
)
print(answer)

# More questions
answer = ask_followup(
    "Who is the billing provider?",
    edi_result,
    val_result,
    llm=my_llm
)
```

**When to Use**:
- Need specific information from EDI
- Want conversational interface
- Building chatbot or Q&A system

---

### 5. `chat(edi_result, val_result, llm)` - Interactive Chat

**Purpose**: Start interactive chat session about EDI file

**Signature**:
```python
def chat(
    edi_result: ParsedEDI,
    val_result: ValidationResult,
    llm: Callable[[str], str]
) -> None
```

**Parameters**:
- `edi_result`: Result from `parse()`
- `val_result`: Result from `validate()`
- `llm`: LLM function (required)

**Returns**: None (interactive CLI)

**Usage**:
```python
# Start chat session
edi_result = parse('claim.edi')
val_result = validate(edi_result)

chat(edi_result, val_result, llm=my_llm)

# User can then type questions:
# You: What is the claim amount?
# Bot: The claim amount is $1,250.00
# You: Are there any errors?
# Bot: Yes, there is 1 error: Invalid NPI format
# You: quit
```

**When to Use**:
- Building interactive CLI tools
- Need exploratory analysis
- Want conversational interface

---

## Data Models

### ParsedEDI

**Structure**:
```python
class ParsedEDI:
    envelope: EnvelopeMeta      # Metadata
    loops: list[Loop]            # Hierarchical loops
    raw: str                     # Original EDI content
```

**Access Patterns**:
```python
result = parse('claim.edi')

# Envelope metadata
result.envelope.transaction_type  # "837P", "837I", "835", "834"
result.envelope.sender_id
result.envelope.receiver_id
result.envelope.interchange_date
result.envelope.interchange_time
result.envelope.version
result.envelope.st_control_number

# Loop navigation
for loop in result.loops:
    print(f"Loop {loop.loop_id}: {len(loop.segments)} segments")
    
    # Find segment
    nm1 = loop.find_segment('NM1')
    if nm1:
        name = nm1.get_value(3)  # Get element 3
    
    # Child loops
    for child in loop.children:
        print(f"  Child: {child.loop_id}")
```

---

### EnvelopeMeta

**Structure**:
```python
class EnvelopeMeta:
    isa_control_number: str
    gs_control_number: str
    st_control_number: str
    sender_id: str
    receiver_id: str
    interchange_date: str
    interchange_time: str
    version: str
    transaction_type: str
```

---

### Loop

**Structure**:
```python
class Loop:
    loop_id: str                 # Loop identifier (e.g., "2000A")
    segments: list[Segment]      # Direct segments
    children: list[Loop]         # Child loops
```

**Methods**:
```python
# Find first segment with ID
segment = loop.find_segment('CLM')

# Find all segments with ID
segments = loop.find_all('SV1')

# Find child loops recursively
child_loops = loop.find_loop('2400')
```

---

### Segment

**Structure**:
```python
class Segment:
    segment_id: str              # Segment ID (e.g., "CLM")
    elements: list[Element]      # Elements (1-based indexing)
    position: int                # Position in file
```

**Methods**:
```python
# Get element by 1-based index
element = segment.get(1)

# Get element value directly
value = segment.get_value(1)

# Example: CLM segment
clm = loop.find_segment('CLM')
claim_id = clm.get_value(1)      # CLM01
claim_amount = clm.get_value(2)  # CLM02
```

---

### Element

**Structure**:
```python
class Element:
    raw: str                     # Raw value
    components: list[str]        # Sub-components (if composite)
```

**Methods**:
```python
# Get composite component by 1-based index
component = element.get(1)

# Example: Composite element
hi = segment.get(1)              # HI01
code = hi.get(1)                 # First component
qualifier = hi.get(2)            # Second component
```

---

### ValidationResult

**Structure**:
```python
class ValidationResult:
    parsed: ParsedEDI            # Parsed EDI data
    errors: list[ValidationError] # Validation errors
```

**Properties**:
```python
result.is_valid          # True if no errors
result.error_count       # Count of errors
result.warning_count     # Count of warnings
```

---

### ValidationError

**Structure**:
```python
class ValidationError:
    code: str                    # Error code
    severity: str                # "error", "warning", "info"
    segment: str                 # Segment ID
    element: str | None          # Element ID (if applicable)
    loop: str | None             # Loop ID (if applicable)
    position: int                # Position in file
    message: str                 # Human-readable message
```

---

## Common Patterns

### Pattern 1: Parse and Extract Data

```python
from validedi import parse

# Parse file
result = parse('claim.edi')

# Extract envelope info
print(f"Transaction: {result.envelope.transaction_type}")
print(f"From: {result.envelope.sender_id}")
print(f"To: {result.envelope.receiver_id}")

# Navigate loops
for loop in result.loops:
    if loop.loop_id == '2000A':  # Billing Provider
        nm1 = loop.find_segment('NM1')
        if nm1:
            provider_name = nm1.get_value(3)
            print(f"Provider: {provider_name}")
```

---

### Pattern 2: Validate and Report Errors

```python
from validedi import validate

# Validate file
result = validate('claim.edi')

# Check validity
if result.is_valid:
    print("✅ File is valid")
else:
    print(f"❌ Found {result.error_count} errors")
    
    # Report errors
    for error in result.errors:
        print(f"\n[{error.severity.upper()}] {error.code}")
        print(f"  Segment: {error.segment}")
        print(f"  Position: {error.position}")
        print(f"  Message: {error.message}")
```

---

### Pattern 3: Batch Processing

```python
from validedi import validate
import glob

# Process all EDI files
for filepath in glob.glob('*.edi'):
    result = validate(filepath)
    
    status = "✅ VALID" if result.is_valid else f"❌ {result.error_count} errors"
    print(f"{filepath}: {status}")
    
    # Log errors
    if not result.is_valid:
        with open(f"{filepath}.errors.txt", 'w') as f:
            for error in result.errors:
                f.write(f"{error.code}: {error.message}\n")
```

---

### Pattern 4: Extract Specific Data (837P Claims)

```python
from validedi import parse

result = parse('claim_837p.edi')

# Find all claims
for loop in result.loops:
    if loop.loop_id == '2300':  # Claim loop
        clm = loop.find_segment('CLM')
        if clm:
            claim_id = clm.get_value(1)
            claim_amount = clm.get_value(2)
            print(f"Claim {claim_id}: ${claim_amount}")
            
            # Find service lines
            for child in loop.children:
                if child.loop_id == '2400':  # Service line
                    sv1 = child.find_segment('SV1')
                    if sv1:
                        procedure = sv1.get_value(1)
                        charge = sv1.get_value(2)
                        print(f"  Service: {procedure} - ${charge}")
```

---

### Pattern 5: Extract Payment Info (835)

```python
from validedi import parse

result = parse('remittance_835.edi')

# Find payment info
for loop in result.loops:
    # Financial info
    bpr = loop.find_segment('BPR')
    if bpr:
        payment_amount = bpr.get_value(2)
        payment_date = bpr.get_value(16)
        print(f"Payment: ${payment_amount} on {payment_date}")
    
    # Payer info
    if loop.loop_id == '1000A':
        nm1 = loop.find_segment('NM1')
        if nm1:
            payer_name = nm1.get_value(3)
            print(f"Payer: {payer_name}")
    
    # Claim payments
    if loop.loop_id == '2100':
        clp = loop.find_segment('CLP')
        if clp:
            claim_id = clp.get_value(1)
            status = clp.get_value(2)
            billed = clp.get_value(3)
            paid = clp.get_value(4)
            print(f"Claim {claim_id}: Billed ${billed}, Paid ${paid}")
```

---

### Pattern 6: LLM-Powered Analysis

```python
from validedi import parse, validate
from validedi.llm import explain, ask_followup
from openai import OpenAI

# Setup LLM
client = OpenAI(api_key="your-key")

def my_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Parse and validate
edi_result = parse('claim.edi')
val_result = validate(edi_result)

# Get explanation
explanation = explain(edi_result, val_result, llm=my_llm)
print(explanation.report)

# Ask questions
questions = [
    "What is the total billed amount?",
    "Who is the billing provider?",
    "Are there any errors?",
    "What diagnosis codes are used?"
]

for question in questions:
    answer = ask_followup(question, edi_result, val_result, llm=my_llm)
    print(f"\nQ: {question}")
    print(f"A: {answer}")
```

---

### Pattern 7: Error Analysis

```python
from validedi import validate
from collections import Counter

result = validate('claim.edi')

# Group errors by type
error_types = Counter(error.code for error in result.errors)

print("Error Summary:")
for code, count in error_types.most_common():
    print(f"  {code}: {count} occurrences")

# Group by severity
by_severity = {}
for error in result.errors:
    by_severity.setdefault(error.severity, []).append(error)

print(f"\nErrors: {len(by_severity.get('error', []))}")
print(f"Warnings: {len(by_severity.get('warning', []))}")
```

---

## Error Handling

### Exception Types

```python
from validedi.utils.exceptions import (
    EDIParseError,              # Parsing failed
    UnsupportedTransactionError, # Unknown transaction type
    ValidationError             # Validation failed
)
```

### Safe Parsing

```python
from validedi import parse
from validedi.utils.exceptions import EDIParseError
import os

def safe_parse(filepath):
    """Safely parse EDI file with error handling."""
    try:
        # Check file exists
        if not os.path.exists(filepath):
            return None, f"File not found: {filepath}"
        
        # Parse
        result = parse(filepath)
        return result, None
        
    except EDIParseError as e:
        return None, f"Parse error: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"

# Usage
result, error = safe_parse('claim.edi')
if error:
    print(f"❌ {error}")
else:
    print(f"✅ Parsed: {result.envelope.transaction_type}")
```

---

### Safe Validation

```python
from validedi import validate

def safe_validate(filepath):
    """Safely validate with comprehensive error handling."""
    try:
        result = validate(filepath)
        
        return {
            'success': True,
            'valid': result.is_valid,
            'errors': result.error_count,
            'warnings': result.warning_count,
            'result': result
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'result': None
        }

# Usage
outcome = safe_validate('claim.edi')
if outcome['success']:
    if outcome['valid']:
        print("✅ Valid EDI")
    else:
        print(f"❌ {outcome['errors']} errors")
else:
    print(f"❌ Failed: {outcome['error']}")
```

---

## Advanced Usage

### Custom Loop Navigation

```python
def find_all_loops_recursive(loop, loop_id):
    """Recursively find all loops with given ID."""
    results = []
    
    if loop.loop_id == loop_id:
        results.append(loop)
    
    for child in loop.children:
        results.extend(find_all_loops_recursive(child, loop_id))
    
    return results

# Usage
result = parse('claim.edi')
all_claims = []
for loop in result.loops:
    all_claims.extend(find_all_loops_recursive(loop, '2300'))

print(f"Found {len(all_claims)} claims")
```

---

### Extract All Segments of Type

```python
def find_all_segments(result, segment_id):
    """Find all segments with given ID across all loops."""
    segments = []
    
    def search_loop(loop):
        segments.extend(loop.find_all(segment_id))
        for child in loop.children:
            search_loop(child)
    
    for loop in result.loops:
        search_loop(loop)
    
    return segments

# Usage
result = parse('claim.edi')
all_nm1 = find_all_segments(result, 'NM1')
print(f"Found {len(all_nm1)} NM1 segments")
```

---

### Data Extraction Helper

```python
def extract_claim_data(result):
    """Extract structured claim data from 837P."""
    claims = []
    
    for loop in result.loops:
        if loop.loop_id == '2300':  # Claim loop
            clm = loop.find_segment('CLM')
            if not clm:
                continue
            
            claim = {
                'claim_id': clm.get_value(1),
                'amount': clm.get_value(2),
                'service_lines': []
            }
            
            # Get service lines
            for child in loop.children:
                if child.loop_id == '2400':
                    sv1 = child.find_segment('SV1')
                    if sv1:
                        claim['service_lines'].append({
                            'procedure': sv1.get_value(1),
                            'charge': sv1.get_value(2),
                            'units': sv1.get_value(4)
                        })
            
            claims.append(claim)
    
    return claims

# Usage
result = parse('claim_837p.edi')
claims = extract_claim_data(result)

for claim in claims:
    print(f"Claim {claim['claim_id']}: ${claim['amount']}")
    for line in claim['service_lines']:
        print(f"  {line['procedure']}: ${line['charge']}")
```

---

## Configuration

### Supported Transaction Types

ValidEDI supports these X12 transaction types:

- **837P**: Professional Health Care Claims
- **837I**: Institutional Health Care Claims
- **835**: Health Care Claim Payment/Remittance Advice
- **834**: Benefit Enrollment and Maintenance

### Validation Rules

60+ built-in validation rules across 4 categories:

1. **Envelope Validation**: ISA/GS/ST structure
2. **Format Validation**: Dates, NPIs, codes
3. **Business Rules**: Required entities, charge totals
4. **Code Set Validation**: Valid code values

### Code Sets

200+ codes included:
- Adjustment Reason Codes (CARC)
- Place of Service Codes
- Entity Identifier Codes
- Relationship Codes
- Date Qualifiers
- ICD-10 codes (common)
- CPT codes (common)

---

## Performance Tips

### 1. Parse Once, Use Multiple Times

```python
# ❌ Bad: Parse multiple times
result1 = validate('claim.edi')
result2 = parse('claim.edi')

# ✅ Good: Parse once
edi_result = parse('claim.edi')
val_result = validate(edi_result)  # Reuses parsed data
```

### 2. Batch Processing

```python
# Process multiple files efficiently
files = glob.glob('*.edi')

results = []
for filepath in files:
    try:
        result = validate(filepath)
        results.append((filepath, result))
    except Exception as e:
        print(f"Failed {filepath}: {e}")

# Analyze results
valid_count = sum(1 for _, r in results if r.is_valid)
print(f"Valid: {valid_count}/{len(results)}")
```

### 3. Selective Validation

```python
# If you only need parsing (faster)
result = parse('claim.edi')

# If you need validation
result = validate('claim.edi')
```

---

## Complete Example: EDI Processing Pipeline

```python
from validedi import parse, validate
from validedi.llm import explain
from openai import OpenAI
import glob
import json

# Setup LLM
client = OpenAI(api_key="your-key")

def my_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def process_edi_file(filepath):
    """Complete EDI processing pipeline."""
    print(f"\n{'='*70}")
    print(f"Processing: {filepath}")
    print('='*70)
    
    # 1. Parse
    try:
        edi_result = parse(filepath)
        print(f"✅ Parsed: {edi_result.envelope.transaction_type}")
    except Exception as e:
        print(f"❌ Parse failed: {e}")
        return None
    
    # 2. Validate
    try:
        val_result = validate(edi_result)
        if val_result.is_valid:
            print("✅ Validation passed")
        else:
            print(f"⚠️  {val_result.error_count} errors, {val_result.warning_count} warnings")
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return None
    
    # 3. Generate explanation
    try:
        explanation = explain(edi_result, val_result, llm=my_llm)
        print("\n" + explanation.report)
    except Exception as e:
        print(f"⚠️  Explanation failed: {e}")
    
    # 4. Extract data
    data = {
        'file': filepath,
        'transaction_type': edi_result.envelope.transaction_type,
        'sender': edi_result.envelope.sender_id,
        'receiver': edi_result.envelope.receiver_id,
        'valid': val_result.is_valid,
        'error_count': val_result.error_count,
        'errors': [
            {
                'code': e.code,
                'severity': e.severity,
                'message': e.message,
                'segment': e.segment
            }
            for e in val_result.errors
        ]
    }
    
    return data

# Process all files
results = []
for filepath in glob.glob('*.edi'):
    data = process_edi_file(filepath)
    if data:
        results.append(data)

# Save results
with open('edi_processing_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Processed {len(results)} files")
```

---

## Quick Troubleshooting

### Issue: "Could not find GS or ST segments"
**Solution**: EDI file is malformed or empty. Check file content.

### Issue: "ISA segment too short"
**Solution**: File doesn't start with valid ISA segment. Verify it's an X12 EDI file.

### Issue: "Unsupported transaction type"
**Solution**: Transaction type not supported. ValidEDI supports 837P, 837I, 835, 834.

### Issue: AttributeError on ParsedEDI
**Solution**: Use `result.envelope.transaction_type` not `result.transaction_type`

### Issue: LLM function not working
**Solution**: Ensure LLM function signature is `(str) -> str`

---

## Summary

### Most Common Operations

```python
# 1. Parse only (fast)
result = parse('file.edi')

# 2. Parse and validate
result = validate('file.edi')

# 3. Get explanation (with LLM)
explanation = explain(edi_result, val_result, llm=my_llm)

# 4. Ask questions
answer = ask_followup("What is the total?", edi_result, val_result, llm=my_llm)

# 5. Navigate data
for loop in result.loops:
    segment = loop.find_segment('CLM')
    value = segment.get_value(1)
```

### Key Points for LLMs

1. **Always use `envelope.transaction_type`** not `transaction_type`
2. **Elements are 1-based indexed** (EDI convention)
3. **Loops are hierarchical** - use `children` to navigate
4. **ValidationResult contains ParsedEDI** - access via `result.parsed`
5. **LLM functions must be `(str) -> str`** signature
6. **File paths and strings both work** for parse/validate

---

**End of Guide**

This guide covers 100% of ValidEDI's public API. Any LLM with this guide can use ValidEDI proficiently.
