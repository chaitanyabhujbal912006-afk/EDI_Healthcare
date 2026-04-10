"""
ValidEDI LLM Integration
========================

LLM-powered explanations, Q&A, and configuration management for EDI validation.

Usage:
    from validedi import parse, validate
    from validedi.llm import (
        explain, ask_followup,
        add_custom_config, get_custom_config, 
        update_custom_config, delete_custom_config,
        list_rule_ids
    )
    
    # Define your LLM function (any provider)
    def my_llm(prompt: str) -> str:
        # Your LLM implementation
        return response
    
    # Parse and validate
    edi_result = parse("file.edi")
    val_result = validate(edi_result)
    
    # Get explanation
    explanation = explain(edi_result, val_result, llm=my_llm)
    print(explanation.report)
    
    # Ask follow-up questions
    answer = ask_followup("What is the total billed?", edi_result, val_result, llm=my_llm)
    print(answer)
    
    # CRUD operations for custom configuration
    
    # Create: Add custom configuration
    result = add_custom_config(
        context="Add a rule to check that claim amounts don't exceed $50,000",
        llm=my_llm,
        config_type="rule"
    )
    
    # Read: Get configuration
    configs = get_custom_config(rule_id="CLM-001")
    all_rules = get_custom_config()  # Get all rules
    
    # Update: Modify existing configuration
    result = update_custom_config(
        rule_id="CLM-001",
        context="Change severity to warning",
        llm=my_llm
    )
    
    # Delete: Remove configuration
    result = delete_custom_config(rule_id="CLM-001")
    
    # List all rule IDs
    ids = list_rule_ids()
"""

from .explainer import LLMExplainer, ExplainResult, explain, ask_followup
from .config_updater import LLMConfigUpdater, ConfigUpdateResult, add_custom_config
from .read import ReadResult, get_custom_config, list_rule_ids
from .update import UpdateResult, update_custom_config
from .delete import DeleteResult, delete_custom_config
from ._exceptions import RuleNotFoundError, RuleConflictError

__all__ = [
    # Explainer
    'LLMExplainer', 
    'ExplainResult', 
    'explain', 
    'ask_followup',
    
    # Config updater (class-based interface)
    'LLMConfigUpdater',
    
    # CRUD operations (function-based interface)
    'add_custom_config',      # Create
    'get_custom_config',      # Read
    'list_rule_ids',          # Read (list)
    'update_custom_config',   # Update
    'delete_custom_config',   # Delete
    
    # Result types
    'ConfigUpdateResult',     # Create result
    'ReadResult',             # Read result
    'UpdateResult',           # Update result
    'DeleteResult',           # Delete result
    
    # Exceptions
    'RuleNotFoundError',
    'RuleConflictError',
]
