"""
BaseValidator - Abstract base class for all transaction validators

Defines the validation contract:
- validate(parse_result: ParseResult) -> List[ValidationError]
- get_rules() -> List[ValidationRule]
- apply_rule(rule: ValidationRule, loop: Loop) -> List[ValidationError]

Provides shared orchestration:
- Traverse loop tree
- Apply rules to each loop/segment
- Collect and deduplicate errors
- Assign severity levels (error vs warning)

All transaction validators inherit from this.
"""
