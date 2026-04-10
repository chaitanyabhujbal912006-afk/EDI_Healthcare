"""
Example: LLM-Powered Configuration Updates

This example demonstrates how to use the LLM config updater to add custom
validation rules and code sets using natural language.

IMPORTANT: This feature requires an LLM provider (OpenAI, Groq, Anthropic, etc.)
"""

import os
from validedi.llm import LLMConfigUpdater, add_custom_config


# ── Setup LLM ─────────────────────────────────────────────────────────────────

def setup_groq_llm():
    """Setup Groq LLM (fast and free)."""
    try:
        from groq import Groq
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("❌ GROQ_API_KEY not found in environment")
            return None
        
        client = Groq(api_key=api_key)
        
        def llm(prompt: str) -> str:
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent config generation
                max_tokens=2000
            )
            return response.choices[0].message.content
        
        return llm
    except ImportError:
        print("❌ Groq not installed. Run: pip install groq")
        return None


def setup_openai_llm():
    """Setup OpenAI LLM."""
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY not found in environment")
            return None
        
        client = OpenAI(api_key=api_key)
        
        def llm(prompt: str) -> str:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            return response.choices[0].message.content
        
        return llm
    except ImportError:
        print("❌ OpenAI not installed. Run: pip install openai")
        return None


# ── Example 1: Add a Custom Validation Rule ──────────────────────────────────

def example_add_validation_rule():
    """Add a custom validation rule using natural language."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Add Custom Validation Rule")
    print("="*70)
    
    # Setup LLM
    llm = setup_groq_llm() or setup_openai_llm()
    if not llm:
        print("⚠️  No LLM available. Skipping example.")
        return
    
    # Create updater
    updater = LLMConfigUpdater(llm=llm, dry_run=True)  # dry_run=True for safety
    
    # Add custom rule using natural language
    context = """
    Add a validation rule that checks if the claim amount in CLM02 exceeds $50,000.
    If it does, flag it as a warning that requires manual review.
    The rule ID should be CLM-AMOUNT-HIGH.
    The message should say "Claim amount exceeds $50,000 - manual review required".
    """
    
    print("\n📝 Request:")
    print(context.strip())
    
    print("\n🤖 Generating configuration...")
    result = updater.add_custom_config(
        context=context,
        config_type="rule"  # or "auto" to let LLM decide
    )
    
    print(f"\n{'✅' if result.success else '❌'} Result: {result}")
    
    if result.success:
        print(f"\n📄 Generated YAML:")
        print("-" * 70)
        print(result.generated_yaml)
        print("-" * 70)
        print(f"\n💾 Would be added to: {result.target_file}")
        print("   (dry_run=True, so file was not modified)")
    else:
        print(f"\n❌ Validation Errors:")
        for error in result.validation_errors:
            print(f"   - {error}")


# ── Example 2: Add a Custom Code Set ─────────────────────────────────────────

def example_add_code_set():
    """Add a custom code set using natural language."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Add Custom Code Set")
    print("="*70)
    
    # Setup LLM
    llm = setup_groq_llm() or setup_openai_llm()
    if not llm:
        print("⚠️  No LLM available. Skipping example.")
        return
    
    # Add custom code set
    context = """
    Create a code set for internal provider specialty codes used by our organization.
    The code set ID should be "internal_provider_specialties".
    
    Include these codes:
    - CARD: Cardiology
    - DERM: Dermatology
    - ENDO: Endocrinology
    - GAST: Gastroenterology
    - NEUR: Neurology
    - ONCO: Oncology
    - ORTH: Orthopedics
    - PEDI: Pediatrics
    """
    
    print("\n📝 Request:")
    print(context.strip())
    
    print("\n🤖 Generating configuration...")
    
    # Use convenience function
    result = add_custom_config(
        context=context,
        llm=llm,
        config_type="code_set",
        dry_run=True
    )
    
    print(f"\n{'✅' if result.success else '❌'} Result: {result}")
    
    if result.success:
        print(f"\n📄 Generated YAML:")
        print("-" * 70)
        print(result.generated_yaml)
        print("-" * 70)
        print(f"\n💾 Would be added to: {result.target_file}")


# ── Example 3: Add Multiple Rules at Once ────────────────────────────────────

def example_add_multiple_rules():
    """Add multiple related rules in one request."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Add Multiple Related Rules")
    print("="*70)
    
    # Setup LLM
    llm = setup_groq_llm() or setup_openai_llm()
    if not llm:
        print("⚠️  No LLM available. Skipping example.")
        return
    
    updater = LLMConfigUpdater(llm=llm, dry_run=True)
    
    context = """
    Add validation rules for our organization's custom requirements:
    
    1. Check that provider NPI numbers start with "1" (individual providers)
       - Rule ID: CUSTOM-NPI-001
       - Severity: warning
       - Message: "Provider NPI should start with 1 for individual providers"
    
    2. Check that claim submission date is not more than 90 days after service date
       - Rule ID: CUSTOM-TIMELY-001
       - Severity: error
       - Message: "Claim submitted more than 90 days after service date"
    
    3. Require that all claims over $10,000 have at least 2 diagnosis codes
       - Rule ID: CUSTOM-DIAG-001
       - Severity: warning
       - Message: "High-value claims should have multiple diagnosis codes"
    """
    
    print("\n📝 Request:")
    print(context.strip())
    
    print("\n🤖 Generating configuration...")
    result = updater.add_custom_config(context=context, config_type="rule")
    
    print(f"\n{'✅' if result.success else '❌'} Result: {result}")
    
    if result.success:
        print(f"\n📄 Generated YAML:")
        print("-" * 70)
        print(result.generated_yaml)
        print("-" * 70)


# ── Example 4: Preview Before Applying ───────────────────────────────────────

def example_preview_config():
    """Preview configuration before applying."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Preview Configuration")
    print("="*70)
    
    # Setup LLM
    llm = setup_groq_llm() or setup_openai_llm()
    if not llm:
        print("⚠️  No LLM available. Skipping example.")
        return
    
    updater = LLMConfigUpdater(llm=llm)
    
    context = """
    Add a rule to validate that patient date of birth in DMG02 is not in the future.
    Rule ID: CUSTOM-DOB-001
    Severity: error
    """
    
    print("\n📝 Request:")
    print(context.strip())
    
    print("\n🔍 Previewing configuration...")
    preview = updater.preview_config(context=context, config_type="rule")
    
    print(f"\n📄 Preview:")
    print("-" * 70)
    print(preview)
    print("-" * 70)
    
    # User can review and then decide to apply
    print("\n💡 To apply this configuration, set dry_run=False")


# ── Example 5: Auto-Detect Configuration Type ────────────────────────────────

def example_auto_detect():
    """Let the LLM automatically detect what type of config to create."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Auto-Detect Configuration Type")
    print("="*70)
    
    # Setup LLM
    llm = setup_groq_llm() or setup_openai_llm()
    if not llm:
        print("⚠️  No LLM available. Skipping example.")
        return
    
    # Example 1: Should detect as "rule"
    context1 = "Make sure all NPI numbers are exactly 10 digits long"
    
    print("\n📝 Request 1:")
    print(context1)
    
    result1 = add_custom_config(context=context1, llm=llm, config_type="auto", dry_run=True)
    print(f"🤖 Detected type: {result1.config_type}")
    
    # Example 2: Should detect as "code_set"
    context2 = """
    Create a list of valid state codes for our region:
    CA, OR, WA, NV, AZ
    """
    
    print("\n📝 Request 2:")
    print(context2)
    
    result2 = add_custom_config(context=context2, llm=llm, config_type="auto", dry_run=True)
    print(f"🤖 Detected type: {result2.config_type}")


# ── Example 6: Real-World Scenario ───────────────────────────────────────────

def example_real_world_scenario():
    """Real-world scenario: Adding organization-specific validation."""
    print("\n" + "="*70)
    print("EXAMPLE 6: Real-World Scenario")
    print("="*70)
    print("\nScenario: Healthcare organization needs to enforce custom business rules")
    
    # Setup LLM
    llm = setup_groq_llm() or setup_openai_llm()
    if not llm:
        print("⚠️  No LLM available. Skipping example.")
        return
    
    updater = LLMConfigUpdater(llm=llm, dry_run=True)
    
    # Business requirement from compliance team
    context = """
    Our compliance team requires the following validation:
    
    For all professional claims (837P), if the place of service code in SV105 
    is "11" (office), then the claim must include a referring provider in loop 2310A.
    
    This should be an error-level validation with the message:
    "Office visits require a referring provider - add loop 2310A with referring physician NPI"
    
    Rule ID should be ORG-REFERRING-001
    """
    
    print("\n📋 Business Requirement:")
    print(context.strip())
    
    print("\n🤖 Translating to technical configuration...")
    result = updater.add_custom_config(context=context, config_type="rule")
    
    if result.success:
        print("\n✅ Configuration generated successfully!")
        print(f"\n📄 Technical Implementation:")
        print("-" * 70)
        print(result.generated_yaml)
        print("-" * 70)
        print("\n💡 This configuration can now be reviewed by technical team")
        print("   and applied to production after approval.")
    else:
        print(f"\n❌ Failed to generate configuration:")
        for error in result.validation_errors:
            print(f"   - {error}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("LLM-POWERED CONFIGURATION UPDATES - EXAMPLES")
    print("="*70)
    print("\nThese examples demonstrate how to add custom validation rules")
    print("and code sets using natural language instead of writing YAML manually.")
    print("\nNote: All examples use dry_run=True for safety.")
    
    # Run examples
    example_add_validation_rule()
    example_add_code_set()
    example_add_multiple_rules()
    example_preview_config()
    example_auto_detect()
    example_real_world_scenario()
    
    print("\n" + "="*70)
    print("EXAMPLES COMPLETE")
    print("="*70)
    print("\n💡 To actually apply configurations:")
    print("   1. Review the generated YAML carefully")
    print("   2. Set dry_run=False")
    print("   3. Backups are created automatically (unless disabled)")
    print("   4. Config cache is invalidated automatically")
    print("\n⚠️  IMPORTANT: Always review generated configurations before applying!")


if __name__ == "__main__":
    main()
