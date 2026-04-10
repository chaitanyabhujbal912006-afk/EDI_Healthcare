# ValidEDI LLM Integration Guide

## Overview

ValidEDI includes LLM-powered explanations that convert complex EDI validation results into plain-English reports. The integration is **provider-agnostic** - you can use any LLM provider (OpenAI, Groq, Bedrock, Gemini, etc.) by passing a simple callable function.

## Key Features

✅ **Provider-Agnostic** - Works with any LLM (OpenAI, Groq, Bedrock, Gemini, Anthropic, etc.)  
✅ **Simple Interface** - Just pass a function that takes a prompt and returns a response  
✅ **Plain-English Reports** - Converts technical EDI data into readable explanations  
✅ **Interactive Q&A** - Ask follow-up questions about your EDI files  
✅ **Configuration Management** - Add custom rules and code sets using natural language  
✅ **Rule-Based Fallback** - Works without an LLM using template-based reports  
✅ **No Lock-In** - Switch providers anytime, no vendor lock-in

---

## Quick Start

### Basic Usage

```python
from validedi import parse, validate
from validedi.llm import explain

# Define your LLM function (example with OpenAI)
from openai import OpenAI
client = OpenAI(api_key="your-key")

def my_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Parse and validate EDI file
edi_result = parse("file.edi")
val_result = validate(edi_result)

# Get plain-English explanation
result = explain(edi_result, val_result, llm=my_llm)
print(result.report)
```

### Without LLM (Rule-Based)

```python
# Works without any LLM - uses template-based reports
result = explain(edi_result, val_result)
print(result.report)
```

---

## LLM Provider Examples

### OpenAI (GPT-4, GPT-3.5)

```python
from openai import OpenAI

client = OpenAI(api_key="sk-...")

def llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1200
    )
    return response.choices[0].message.content
```

**Install:** `pip install openai`  
**API Key:** https://platform.openai.com/api-keys

---

### Groq (Fast, Free Tier)

```python
from groq import Groq

client = Groq(api_key="gsk_...")

def llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1200
    )
    return response.choices[0].message.content
```

**Install:** `pip install groq`  
**API Key:** https://console.groq.com/keys  
**Models:** llama-3.1-70b-versatile, mixtral-8x7b-32768, gemma-7b-it

---

### AWS Bedrock (Claude, Llama)

```python
import boto3
import json

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def llm(prompt: str) -> str:
    body = json.dumps({
        "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
        "max_tokens_to_sample": 1200,
        "temperature": 0.3,
    })
    
    response = bedrock.invoke_model(
        modelId="anthropic.claude-v2",
        body=body
    )
    
    response_body = json.loads(response['body'].read())
    return response_body['completion']
```

**Install:** `pip install boto3`  
**Setup:** Configure AWS credentials  
**Models:** anthropic.claude-v2, meta.llama2-70b-chat-v1

---

### Google Gemini

```python
import google.generativeai as genai

genai.configure(api_key="AIza...")
model = genai.GenerativeModel('gemini-pro')

def llm(prompt: str) -> str:
    response = model.generate_content(prompt)
    return response.text
```

**Install:** `pip install google-generativeai`  
**API Key:** https://makersuite.google.com/app/apikey

---

### Anthropic Claude

```python
from anthropic import Anthropic

client = Anthropic(api_key="sk-ant-...")

def llm(prompt: str) -> str:
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1200,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

**Install:** `pip install anthropic`  
**API Key:** https://console.anthropic.com/

---

### Azure OpenAI

```python
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key="your-key",
    api_version="2024-02-01",
    azure_endpoint="https://your-resource.openai.azure.com"
)

def llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",  # Your deployment name
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
```

**Install:** `pip install openai`  
**Setup:** Azure OpenAI resource required

---

## API Reference

### Function-Based API

#### `explain(edi_result, val_result, llm=None, force_rule_based=False)`

Generate a plain-English explanation of the EDI file.

**Parameters:**
- `edi_result` - Parsed EDI result from `parse()`
- `val_result` - Validation result from `validate()`
- `llm` - Optional callable that takes a prompt string and returns a response string
- `force_rule_based` - If True, skip LLM and use rule-based templates

**Returns:** `ExplainResult` with:
- `report` (str) - The generated explanation
- `source` (str) - "llm" or "rule_based"
- `metadata` (dict) - Additional info

**Example:**
```python
result = explain(edi_result, val_result, llm=my_llm)
print(result.report)
print(f"Generated by: {result.source}")
```

---

#### `ask_followup(question, edi_result, val_result, llm=None)`

Answer a follow-up question about the EDI file.

**Parameters:**
- `question` (str) - User's question
- `edi_result` - Parsed EDI result
- `val_result` - Validation result
- `llm` - Optional LLM callable

**Returns:** Answer string

**Example:**
```python
answer = ask_followup(
    "What is the total billed amount?",
    edi_result,
    val_result,
    llm=my_llm
)
print(answer)
```

---

### Class-Based API

#### `LLMExplainer(llm=None)`

Reusable explainer instance.

**Parameters:**
- `llm` - Optional LLM callable

**Methods:**
- `explain(edi_result, val_result, force_rule_based=False)` - Generate explanation
- `ask_followup(question, edi_result, val_result)` - Answer questions

**Example:**
```python
from validedi.llm import LLMExplainer

explainer = LLMExplainer(llm=my_llm)

# Process multiple files
for filepath in files:
    edi_result = parse(filepath)
    val_result = validate(edi_result)
    
    result = explainer.explain(edi_result, val_result)
    print(result.report)
    
    answer = explainer.ask_followup("Any errors?", edi_result, val_result)
    print(answer)
```

---

## Report Structure

Generated reports include these sections:

### 1. OVERVIEW
- Transaction type and purpose
- High-level summary (2-3 sentences)

### 2. KEY PARTIES
- Sender/Receiver
- Billing Provider/Payer
- Submitter/Payee

### 3. FINANCIAL SUMMARY
- Total amounts
- Claim counts
- Payment details
- Dates

### 4. VALIDATION STATUS
- Plain-language explanation of errors/warnings
- Specific fix instructions for each issue
- Severity indicators (❌ error, ⚠️ warning, ℹ️ info)

### 5. ACTION ITEMS
- What to do next
- Who needs to take action
- Priority order

---

## Example Output

### LLM-Generated Report

```
OVERVIEW
--------
This is a Professional Health Care Claim (837P) submission from ABC Medical
Group to BlueCross BlueShield. It contains 3 outpatient claims totaling
$4,250.00 for services rendered in March 2024.

KEY PARTIES
-----------
• Submitter: ABC Medical Group (ID: 12345)
• Billing Provider: Dr. Jane Smith (NPI: 1234567890)
• Payer: BlueCross BlueShield (ID: BCBS001)

FINANCIAL SUMMARY
-----------------
• Total Claims: 3
• Total Billed: $4,250.00
• Service Period: March 1-15, 2024
• Submission Date: March 20, 2024

VALIDATION STATUS
-----------------
✅ File is structurally valid with no critical errors.

⚠️  Warning: CLM06 (Provider Signature on File) is missing on Claim #2.
    FIX: Set CLM06 to 'Y' if provider signature is on file, or 'N' if not.
    This field is required by most payers and may cause claim rejection.

ACTION ITEMS
------------
1. Correct the missing CLM06 value on Claim #2 before resubmission
2. Verify all NPI numbers are current and active
3. Submit to payer clearinghouse for processing
4. Expect remittance (835) within 14-30 days
```

---

## Interactive Chatbot

ValidEDI includes an interactive chatbot for exploring EDI files:

```bash
python examples/llm_chatbot.py path/to/file.edi
```

**Features:**
- Ask questions in plain English
- Get instant answers about your EDI file
- View full reports and summaries
- Interactive command-line interface

**Example Questions:**
- "What is the total billed amount?"
- "How many claims are in this file?"
- "What errors need to be fixed?"
- "Who is the billing provider?"
- "Are there any critical errors?"

---

## Advanced Usage

### Custom LLM Wrapper

```python
class MonitoredLLM:
    """Custom LLM wrapper with logging."""
    
    def __init__(self, base_llm):
        self.base_llm = base_llm
        self.call_count = 0
    
    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        print(f"LLM Call #{self.call_count}")
        return self.base_llm(prompt)

# Use it
monitored_llm = MonitoredLLM(my_llm)
result = explain(edi_result, val_result, llm=monitored_llm)
```

### Error Handling

```python
try:
    result = explain(edi_result, val_result, llm=my_llm)
    if result.source == "rule_based":
        print("⚠️  LLM failed, using rule-based fallback")
    print(result.report)
except Exception as e:
    print(f"Error: {e}")
```

### Batch Processing

```python
explainer = LLMExplainer(llm=my_llm)

for filepath in glob.glob("*.edi"):
    edi_result = parse(filepath)
    val_result = validate(edi_result)
    result = explainer.explain(edi_result, val_result)
    
    # Save report
    with open(f"{filepath}.report.txt", "w") as f:
        f.write(result.report)
```

---

## Best Practices

### 1. Choose the Right Provider

- **OpenAI GPT-4** - Best quality, most expensive
- **Groq** - Fast, free tier, good quality
- **Anthropic Claude** - Great for healthcare, good quality
- **AWS Bedrock** - Enterprise, multiple models
- **Google Gemini** - Free tier, good for testing

### 2. Optimize Costs

```python
# Use cheaper models for simple questions
def cheap_llm(prompt: str) -> str:
    # Use GPT-3.5 instead of GPT-4
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Cheaper
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
```

### 3. Handle Rate Limits

```python
import time
from functools import wraps

def rate_limited(max_per_minute=10):
    min_interval = 60.0 / max_per_minute
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

@rate_limited(max_per_minute=10)
def llm(prompt: str) -> str:
    # Your LLM call
    pass
```

### 4. Cache Results

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_llm(prompt: str) -> str:
    # Your LLM call
    pass
```

---

## Troubleshooting

### "No LLM available"

**Problem:** LLM callable is None or not provided.

**Solution:** Pass an LLM function:
```python
result = explain(edi_result, val_result, llm=my_llm)
```

### "Error calling LLM"

**Problem:** LLM function raised an exception.

**Solution:** Check your API key, network connection, and error message. The system will fall back to rule-based templates.

### Empty or Invalid Responses

**Problem:** LLM returns empty or malformed response.

**Solution:** System automatically falls back to rule-based templates. Check your LLM configuration and prompt.

### Rate Limit Errors

**Problem:** Too many API calls.

**Solution:** Implement rate limiting (see Best Practices) or use a provider with higher limits.

---

## FAQ

**Q: Do I need an LLM to use ValidEDI?**  
A: No! ValidEDI works perfectly without an LLM using rule-based templates. LLM is optional for enhanced explanations.

**Q: Which LLM provider is best?**  
A: Depends on your needs:
- Best quality: OpenAI GPT-4
- Best value: Groq (free tier)
- Best for healthcare: Anthropic Claude
- Best for enterprise: AWS Bedrock

**Q: Can I use local models?**  
A: Yes! Any callable that takes a prompt and returns a response works. Use Ollama, LM Studio, or any local model.

**Q: How much does it cost?**  
A: Depends on provider:
- Groq: Free tier available
- OpenAI: ~$0.01-0.03 per explanation
- Anthropic: ~$0.01-0.02 per explanation
- Gemini: Free tier available

**Q: Is my data sent to third parties?**  
A: Only if you use a cloud LLM provider. For privacy, use local models or rule-based templates.

**Q: Can I customize the prompts?**  
A: Yes! Fork the library and modify `validedi/src/validedi/llm/prompts.py`.

---

## Examples

See `examples/llm_usage.py` for comprehensive examples with all major providers.

See `examples/llm_chatbot.py` for an interactive chatbot implementation.

---

## Support

For issues or questions:
- GitHub Issues: [your-repo-url]
- Documentation: [your-docs-url]
- Email: [your-email]


---

## Configuration Management (NEW in v0.3.2)

### LLM-Powered Custom Rules

Add custom validation rules and code sets using natural language instead of manually writing YAML.

```python
from validedi.llm import add_custom_config

# Add a custom validation rule
result = add_custom_config(
    context="""
    Add a validation rule that checks if the claim amount in CLM02 
    exceeds $50,000. If it does, flag it as a warning that requires 
    manual review. The rule ID should be CLM-AMOUNT-HIGH.
    """,
    llm=my_llm,
    config_type="rule"
)

if result.success:
    print(f"✅ Added to {result.target_file}")
    print(result.generated_yaml)
else:
    print(f"❌ Errors: {result.validation_errors}")
```

### Add Custom Code Sets

```python
result = add_custom_config(
    context="""
    Create a code set for internal provider specialty codes:
    - CARD: Cardiology
    - DERM: Dermatology
    - ENDO: Endocrinology
    
    Code set ID: internal_provider_specialties
    """,
    llm=my_llm,
    config_type="code_set"
)
```

### Preview Before Applying

```python
from validedi.llm import LLMConfigUpdater

updater = LLMConfigUpdater(llm=my_llm)

# Preview without modifying files
preview = updater.preview_config(
    context="Add a rule to validate NPI format",
    config_type="rule"
)
print(preview)

# Apply if satisfied
result = updater.add_custom_config(
    context="Add a rule to validate NPI format",
    config_type="rule"
)
```

### Safety Features

- **Dry Run Mode**: Test without modifying files
- **Automatic Backups**: Backups created before modifications
- **Multi-Layer Validation**: YAML syntax, schema, ID conflicts
- **Cache Invalidation**: Config cache automatically cleared

For complete documentation, see [LLM_CONFIG_UPDATER.md](LLM_CONFIG_UPDATER.md)

---
