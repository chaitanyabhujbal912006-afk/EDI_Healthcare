"""
Configuration loader for YAML-based transaction definitions.
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from threading import Lock

from validedi.utils.exceptions import BadConfigError


@dataclass
class LoopConfig:
    """Configuration for a single loop."""
    id: str
    parent_id: str | None
    trigger_segment: str
    trigger_qualifier: dict[str, Any] | None
    required_segments: list[str]
    rules: list[str]


@dataclass
class RuleConfig:
    """Configuration for a validation rule."""
    id: str
    type: str  # 'regex', 'code_set', 'composite_code_set', 'expression', 'builtin',
               # 'required_segment', 'required_element', 'required_entity',
               # 'numeric_range', 'numeric_validation', 'date_format',
               # 'control_number_match', 'segment_count', 'paired_segments',
               # 'sequential_numbering', 'minimum_count', 'conditional_required'
    severity: str
    message: str
    target: str | None = None
    pattern: str | None = None
    code_set_id: str | None = None
    allowed_values: list | None = None       # inline allowed values for code_set rules
    component: int | None = None             # for composite_code_set: component index (1-based)
    expression: str | None = None
    handler: str | None = None
    loop: str | None = None
    scope: str | None = None
    # control_number_match
    source: str | None = None               # e.g. 'ISA13'
    # numeric_range
    min_value: float | None = None
    max_value: float | None = None
    # element_count / minimum_count
    expected_count: int | None = None
    min_count: int | None = None
    # paired_segments
    segment_pair: list | None = None
    # required_entity
    entity_code: str | None = None
    # date_format
    format_qualifier: str | None = None
    expected_format: str | None = None
    # conditional_required
    condition_segment: str | None = None
    required_segment: str | None = None
    # suggestion shown to user
    suggestion: str | None = None
    # optional: limit rule to specific transaction types (e.g. ['835', '837p'])
    transaction_types: list | None = None


@dataclass
class TransactionConfig:
    """Complete configuration for a transaction type."""
    transaction_type: str
    loops: list[LoopConfig] = field(default_factory=list)
    rules: dict[str, RuleConfig] = field(default_factory=dict)
    code_sets: dict[str, set[str]] = field(default_factory=dict)


class ConfigLoader:
    """Loads and caches YAML configuration files."""
    
    def __init__(self):
        self._cache: dict[str, TransactionConfig] = {}
        self._lock = Lock()
        self._config_dir = Path(__file__).parent.parent / 'config'
        
    def get_config(self, transaction_type: str) -> TransactionConfig:
        """
        Get configuration for a transaction type.
        
        Args:
            transaction_type: Transaction type (e.g., '837p', '835')
            
        Returns:
            TransactionConfig object
            
        Raises:
            BadConfigError: If configuration is invalid or not found
        """
        # Check cache first
        with self._lock:
            if transaction_type in self._cache:
                return self._cache[transaction_type]
        
        # Load from YAML
        config = self._load_transaction_config(transaction_type)
        
        # Cache and return
        with self._lock:
            self._cache[transaction_type] = config
        
        return config

    
    def _load_transaction_config(self, transaction_type: str) -> TransactionConfig:
        """Load transaction configuration from YAML files."""
        # Find config file from registry
        registry_path = self._config_dir / 'registry.yaml'
        if not registry_path.exists():
            raise BadConfigError(
                f'Registry file not found: {registry_path}',
                config_file=str(registry_path)
            )
        
        with open(registry_path, 'r') as f:
            registry = yaml.safe_load(f)
        
        # Find matching transaction
        config_file = None
        for txn in registry.get('transactions', []):
            if txn.get('transaction_type') == transaction_type:
                config_file = txn.get('config_file')
                break
        
        if not config_file:
            raise BadConfigError(
                f'Transaction type {transaction_type} not found in registry',
                config_file=str(registry_path)
            )
        
        # Load transaction YAML
        txn_path = self._config_dir / config_file
        if not txn_path.exists():
            raise BadConfigError(
                f'Transaction config file not found: {txn_path}',
                config_file=str(txn_path)
            )
        
        with open(txn_path, 'r') as f:
            txn_data = yaml.safe_load(f)
        
        # Parse loops
        loops = []
        for loop_data in txn_data.get('loops', []):
            loops.append(LoopConfig(
                id=loop_data['id'],
                parent_id=loop_data.get('parent_id'),
                trigger_segment=loop_data['trigger_segment'],
                trigger_qualifier=loop_data.get('trigger_qualifier'),
                required_segments=loop_data.get('required_segments', []),
                rules=loop_data.get('rules', [])
            ))
        
        # Load all rules
        rules = self._load_all_rules()
        
        # Load all code sets
        code_sets = self._load_all_code_sets()
        
        return TransactionConfig(
            transaction_type=transaction_type,
            loops=loops,
            rules=rules,
            code_sets=code_sets
        )
    
    def _load_all_rules(self) -> dict[str, RuleConfig]:
        """Load all rule definitions from rules/ directory."""
        rules = {}
        rules_dir = self._config_dir / 'rules'
        
        if not rules_dir.exists():
            return rules
        
        for rule_file in rules_dir.glob('*.yaml'):
            with open(rule_file, 'r') as f:
                rule_data = yaml.safe_load(f)
            
            for rule in rule_data.get('rules', []):
                rules[rule['id']] = RuleConfig(
                    id=rule['id'],
                    type=rule['type'],
                    severity=rule['severity'],
                    message=rule['message'],
                    target=rule.get('target'),
                    pattern=rule.get('pattern'),
                    code_set_id=rule.get('code_set_id'),
                    allowed_values=rule.get('allowed_values'),
                    component=rule.get('component'),
                    expression=rule.get('expression'),
                    handler=rule.get('handler'),
                    loop=rule.get('loop'),
                    scope=rule.get('scope'),
                    source=rule.get('source'),
                    min_value=rule.get('min_value'),
                    max_value=rule.get('max_value'),
                    expected_count=rule.get('expected_count'),
                    min_count=rule.get('min_count'),
                    segment_pair=rule.get('segment_pair'),
                    entity_code=rule.get('entity_code'),
                    format_qualifier=rule.get('format_qualifier'),
                    expected_format=rule.get('expected_format'),
                    condition_segment=rule.get('condition_segment'),
                    required_segment=rule.get('required_segment'),
                    suggestion=rule.get('suggestion'),
                    transaction_types=rule.get('transaction_types'),
                )
        
        return rules
    
    def _load_all_code_sets(self) -> dict[str, set[str]]:
        """Load all code sets from code_sets/ directory."""
        code_sets = {}
        code_sets_dir = self._config_dir / 'code_sets'
        
        if not code_sets_dir.exists():
            return code_sets
        
        for code_file in code_sets_dir.glob('*.yaml'):
            with open(code_file, 'r') as f:
                code_data = yaml.safe_load(f)
            
            code_set_id = code_data.get('code_set_id')
            codes = code_data.get('codes', [])
            
            if code_set_id:
                code_sets[code_set_id] = set(codes)
        
        return code_sets
    
    def invalidate_cache(self):
        """Clear the configuration cache."""
        with self._lock:
            self._cache.clear()


# Global instance
_loader = ConfigLoader()


def get_config(transaction_type: str) -> TransactionConfig:
    """Get configuration for a transaction type."""
    return _loader.get_config(transaction_type)


def invalidate_cache():
    """Invalidate the configuration cache."""
    _loader.invalidate_cache()
