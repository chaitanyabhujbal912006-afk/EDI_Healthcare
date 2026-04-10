"""
Example demonstrating CRUD operations for ValidEDI custom rules.

This example shows how to Create, Read, Update, and Delete custom validation rules
using both the function-based and class-based interfaces.
"""

import os
from validedi.llm import (
    LLMConfigUpdater,
    add_custom_config,
    get_custom_config,
    list_rule_ids,
    update_custom_config,
    delete_custom_config,
    RuleNotFoundError
)


def get_llm():
    """
    Get LLM callable based on environment.
    
    Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your environment.
    """
    if os.getenv('OPENAI_API_KEY'):
        from openai import OpenAI
        client = OpenAI()
        
        def llm(prompt: str) -> str:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            return response.choices[0].message.content
        
        return llm
    
    elif os.getenv('ANTHROPIC_API_KEY'):
        from anthropic import Anthropic
        client = Anthropic()
        
        def llm(prompt: str) -> str:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        
        return llm
    
    else:
        raise ValueError(
            "Please set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable"
        )


def example_function_based():
    """Example using function-based interface."""
    print("=" * 60)
    print("FUNCTION-BASED INTERFACE EXAMPLE")
    print("=" * 60)
    
    llm = get_llm()
    
    # 1. CREATE: Add a new rule
    print("\n1. CREATE: Adding a new custom rule...")
    result = add_custom_config(
        context="""
        Add a validation rule with ID 'DEMO-NPI-001' that checks if NPI numbers 
        in the NM109 element are exactly 10 digits. Use regex pattern validation.
        Severity should be 'error' and include a helpful message.
        """,
        llm=llm,
        config_type="rule",
        target_file="rules_core.yaml",
        dry_run=True  # Set to False to actually create
    )
    
    if result.success:
        print(f"✅ Rule would be added to: {result.target_file}")
        print(f"\nGenerated YAML:\n{result.generated_yaml}")
    else:
        print(f"❌ Failed: {result.validation_errors}")
        return
    
    # For demo purposes, let's assume the rule was created with ID 'DEMO-NPI-001'
    demo_rule_id = 'DEMO-NPI-001'
    
    # 2. READ: Get the rule
    print(f"\n2. READ: Retrieving rule {demo_rule_id}...")
    try:
        results = get_custom_config(rule_id=demo_rule_id)
        if results:
            rule = results[0]
            print(f"✅ Found rule in: {rule.source_file}")
            print(f"\nRule details:")
            print(f"  ID: {rule.parsed_dict['id']}")
            print(f"  Type: {rule.parsed_dict['type']}")
            print(f"  Severity: {rule.parsed_dict['severity']}")
            print(f"  Message: {rule.parsed_dict['message']}")
    except RuleNotFoundError:
        print(f"⚠️  Rule {demo_rule_id} not found (expected in dry_run mode)")
    
    # 3. LIST: Show all rules
    print("\n3. LIST: Showing all custom rules...")
    ids = list_rule_ids(config_type="rule")
    print(f"Total rules: {len(ids)}")
    print("\nFirst 10 rules:")
    for rule_id, source_file in ids[:10]:
        print(f"  {rule_id:20s} -> {source_file}")
    
    # 4. UPDATE: Modify the rule
    print(f"\n4. UPDATE: Updating rule {demo_rule_id}...")
    try:
        result = update_custom_config(
            rule_id=demo_rule_id,
            context="Change the severity from 'error' to 'warning' and make the message more friendly",
            llm=llm,
            dry_run=True  # Set to False to actually update
        )
        
        if result.success:
            print(f"✅ Rule would be updated in: {result.source_file}")
            print(f"\nOld YAML:\n{result.old_yaml}")
            print(f"\nNew YAML:\n{result.new_yaml}")
        else:
            print(f"❌ Failed: {result.validation_errors}")
    except RuleNotFoundError:
        print(f"⚠️  Rule {demo_rule_id} not found (expected in dry_run mode)")
    
    # 5. DELETE: Remove the rule
    print(f"\n5. DELETE: Deleting rule {demo_rule_id}...")
    try:
        result = delete_custom_config(
            rule_id=demo_rule_id,
            dry_run=True  # Set to False to actually delete
        )
        
        if result.success:
            print(f"✅ Rule would be deleted from: {result.source_file}")
            print(f"\nDeleted YAML:\n{result.deleted_yaml}")
        else:
            print(f"❌ Failed: {result.validation_errors}")
    except RuleNotFoundError:
        print(f"⚠️  Rule {demo_rule_id} not found (expected in dry_run mode)")


def example_class_based():
    """Example using class-based interface."""
    print("\n\n" + "=" * 60)
    print("CLASS-BASED INTERFACE EXAMPLE")
    print("=" * 60)
    
    llm = get_llm()
    
    # Initialize updater
    updater = LLMConfigUpdater(
        llm=llm,
        create_backups=True,
        dry_run=True  # Set to False for actual operations
    )
    
    # 1. CREATE
    print("\n1. CREATE: Adding a new rule...")
    result = updater.add_custom_config(
        context="""
        Add a rule with ID 'DEMO-CLM-001' to validate that claim amounts 
        in CLM02 are positive numbers with exactly 2 decimal places.
        Use regex validation with severity 'error'.
        """,
        config_type="rule"
    )
    
    if result.success:
        print(f"✅ Rule would be added")
        print(f"Generated YAML:\n{result.generated_yaml}")
    else:
        print(f"❌ Failed: {result.validation_errors}")
    
    # 2. READ
    print("\n2. READ: Getting all error-severity rules...")
    error_rules = updater.get(filters={"severity": "error"})
    print(f"Found {len(error_rules)} error-severity rules")
    
    # Show first 5
    print("\nFirst 5 error rules:")
    for rule in error_rules[:5]:
        print(f"  {rule.rule_id:20s} - {rule.parsed_dict.get('message', 'N/A')[:50]}")
    
    # 3. LIST
    print("\n3. LIST: Listing all rules...")
    ids = updater.list(config_type="rule")
    print(f"Total: {len(ids)} rules")
    
    # 4. UPDATE
    print("\n4. UPDATE: Updating a rule...")
    if ids:
        # Update the first rule as an example
        first_rule_id = ids[0][0]
        print(f"Updating rule: {first_rule_id}")
        
        try:
            result = updater.update(
                rule_id=first_rule_id,
                context="Add a suggestion field with helpful guidance"
            )
            
            if result.success:
                print(f"✅ Rule would be updated")
                print(f"Changes would be made to: {result.source_file}")
            else:
                print(f"❌ Failed: {result.validation_errors}")
        except RuleNotFoundError as e:
            print(f"⚠️  {e}")
    
    # 5. DELETE
    print("\n5. DELETE: Deleting a rule...")
    demo_rule_id = 'DEMO-CLM-001'
    try:
        result = updater.delete(rule_id=demo_rule_id)
        
        if result.success:
            print(f"✅ Rule would be deleted")
        else:
            print(f"❌ Failed: {result.validation_errors}")
    except RuleNotFoundError:
        print(f"⚠️  Rule {demo_rule_id} not found (expected in dry_run mode)")


def example_filters():
    """Example showing advanced filtering."""
    print("\n\n" + "=" * 60)
    print("ADVANCED FILTERING EXAMPLE")
    print("=" * 60)
    
    # Get rules by severity
    print("\n1. Get all warning-severity rules:")
    warnings = get_custom_config(filters={"severity": "warning"})
    print(f"Found {len(warnings)} warning rules")
    
    # Get rules by type
    print("\n2. Get all regex rules:")
    regex_rules = get_custom_config(filters={"type": "regex"})
    print(f"Found {len(regex_rules)} regex rules")
    
    # Get all rules and filter manually
    print("\n3. Get rules with 'NPI' in message:")
    all_rules = get_custom_config()
    npi_rules = [
        r for r in all_rules 
        if 'NPI' in r.parsed_dict.get('message', '').upper()
    ]
    print(f"Found {len(npi_rules)} rules mentioning NPI")
    for rule in npi_rules[:3]:
        print(f"  {rule.rule_id}: {rule.parsed_dict['message']}")


def example_error_handling():
    """Example showing error handling."""
    print("\n\n" + "=" * 60)
    print("ERROR HANDLING EXAMPLE")
    print("=" * 60)
    
    # 1. Handle RuleNotFoundError
    print("\n1. Handling RuleNotFoundError:")
    try:
        results = get_custom_config(rule_id="NONEXISTENT-RULE")
    except RuleNotFoundError as e:
        print(f"✅ Caught expected error: {e}")
    
    # 2. Check result success
    print("\n2. Checking result success:")
    llm = get_llm()
    result = add_custom_config(
        context="Invalid rule without required fields",
        llm=llm,
        dry_run=True
    )
    
    if not result.success:
        print(f"✅ Validation caught errors:")
        for error in result.validation_errors:
            print(f"  - {error}")
    
    # 3. Dry run before actual operation
    print("\n3. Using dry_run for safety:")
    result = delete_custom_config(
        rule_id="ENV-001",  # Core rule
        dry_run=True
    )
    
    if result.success:
        print(f"✅ Dry run successful - would delete:")
        print(f"  Rule: {result.rule_id}")
        print(f"  From: {result.source_file}")
        print(f"  Content: {result.deleted_yaml[:100]}...")
        print("\n⚠️  Set dry_run=False to actually delete")


if __name__ == '__main__':
    print("ValidEDI CRUD Operations Examples")
    print("=" * 60)
    print("\nNote: All examples use dry_run=True by default.")
    print("Set dry_run=False to perform actual operations.")
    print("\nMake sure to set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    print("=" * 60)
    
    try:
        # Run examples
        example_function_based()
        example_class_based()
        example_filters()
        example_error_handling()
        
        print("\n\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)
        
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("\nPlease set one of these environment variables:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
