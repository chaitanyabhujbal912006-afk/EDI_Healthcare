"""
Custom exceptions for LLM config operations.
"""


class RuleNotFoundError(Exception):
    """Raised when a rule ID cannot be found in any file."""
    
    def __init__(self, rule_id: str, config_type: str = "rule"):
        self.rule_id = rule_id
        self.config_type = config_type
        super().__init__(f"{config_type.capitalize()} with ID '{rule_id}' not found in any configuration file")


class RuleConflictError(Exception):
    """Raised when a rule ID already exists (on Create/Update)."""
    
    def __init__(self, rule_id: str, source_file: str, config_type: str = "rule"):
        self.rule_id = rule_id
        self.source_file = source_file
        self.config_type = config_type
        super().__init__(f"{config_type.capitalize()} ID '{rule_id}' already exists in {source_file}")
