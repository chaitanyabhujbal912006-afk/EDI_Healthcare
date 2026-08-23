"""
Tests for LLM-powered configuration updater.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from validedi.llm.config_updater import LLMConfigUpdater, ConfigUpdateResult


# ── Mock LLM ──────────────────────────────────────────────────────────────────

class MockLLM:
    """Mock LLM for testing."""
    
    def __init__(self, responses: dict = None):
        """
        Initialize mock LLM with predefined responses.
        
        Args:
            responses: Dict mapping prompt keywords to responses
        """
        self.responses = responses or {}
        self.calls = []
    
    def __call__(self, prompt: str) -> str:
        """Mock LLM call."""
        self.calls.append(prompt)
        
        # Return predefined response based on prompt content
        for keyword, response in self.responses.items():
            if keyword.lower() in prompt.lower():
                return response
        
        # Default responses
        if "available files" in prompt.lower() or "which configuration file" in prompt.lower():
            return "rules_core.yaml"
        elif "determine the configuration type" in prompt.lower() or "detect configuration type" in prompt.lower():
            return "rule"
        elif "validation checklist" in prompt.lower() or ("validation" in prompt.lower() and "checklist" in prompt.lower()):
            return "VALID"
        else:
            # Generate a simple rule
            return """- id: 'TEST-001'
  type: 'regex'
  target: 'TEST'
  pattern: '^[0-9]+$'
  severity: 'error'
  message: 'Test validation rule'"""


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory structure."""
    temp_dir = tempfile.mkdtemp()
    config_dir = Path(temp_dir) / 'config'
    
    # Create directory structure
    (config_dir / 'rules').mkdir(parents=True)
    (config_dir / 'code_sets').mkdir(parents=True)
    (config_dir / 'transactions').mkdir(parents=True)
    
    # Create sample rules file
    rules_file = config_dir / 'rules' / 'rules_core.yaml'
    rules_file.write_text("""rules:
  - id: 'EXISTING-001'
    type: 'required_segment'
    target: 'ISA'
    severity: 'error'
    message: 'ISA segment is required'
""")
    
    # Create sample code set file
    code_set_file = config_dir / 'code_sets' / 'test_codes.yaml'
    code_set_file.write_text("""code_set_id: 'test_codes'
description: 'Test codes'
codes:
  - 'A'
  - 'B'
  - 'C'
""")
    
    yield config_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    return MockLLM()


@pytest.fixture
def updater(mock_llm, temp_config_dir):
    """Create a config updater with mock LLM and temp directory."""
    return LLMConfigUpdater(
        llm=mock_llm,
        config_dir=temp_config_dir,
        create_backups=False,  # Disable backups for tests
        dry_run=True  # Safe mode for tests
    )


# ── Tests: Initialization ─────────────────────────────────────────────────────

def test_init_requires_llm():
    """Test that LLM is required."""
    with pytest.raises(ValueError, match="LLM callable is required"):
        LLMConfigUpdater(llm=None)


def test_init_validates_config_dir():
    """Test that config directory must exist."""
    with pytest.raises(ValueError, match="Config directory not found"):
        LLMConfigUpdater(llm=lambda x: x, config_dir="/nonexistent/path")


def test_init_with_valid_config(mock_llm, temp_config_dir):
    """Test successful initialization."""
    updater = LLMConfigUpdater(llm=mock_llm, config_dir=temp_config_dir)
    assert updater.config_dir == temp_config_dir
    assert updater.rules_dir == temp_config_dir / 'rules'
    assert updater.code_sets_dir == temp_config_dir / 'code_sets'


# ── Tests: Config Type Detection ──────────────────────────────────────────────

def test_detect_config_type_rule(updater):
    """Test detecting rule configuration type."""
    context = "Add a validation rule to check that ISA segment exists"
    config_type = updater._detect_config_type(context)
    assert config_type == "rule"


def test_detect_config_type_code_set(updater):
    """Test detecting code set configuration type."""
    mock_llm = MockLLM(responses={"configuration type": "code_set"})
    updater_with_mock = LLMConfigUpdater(
        llm=mock_llm,
        config_dir=updater.config_dir,
        dry_run=True
    )
    
    context = "Create a list of valid state codes: CA, OR, WA"
    config_type = updater_with_mock._detect_config_type(context)
    assert config_type == "code_set"


# ── Tests: Target File Detection ──────────────────────────────────────────────

def test_detect_target_file_existing(updater):
    """Test detecting existing target file."""
    context = "Add a rule to rules_core.yaml"
    target_file = updater._detect_target_file(context, "rule")
    assert target_file == "rules_core.yaml"


def test_detect_target_file_new(updater):
    """Test detecting new file creation."""
    mock_llm = MockLLM(responses={"available files": "NEW:custom_rules.yaml"})
    updater_with_mock = LLMConfigUpdater(
        llm=mock_llm,
        config_dir=updater.config_dir,
        dry_run=True
    )
    
    context = "Create a new file for custom rules"
    target_file = updater_with_mock._detect_target_file(context, "rule")
    assert target_file.startswith("NEW:")


# ── Tests: YAML Generation ────────────────────────────────────────────────────

def test_generate_config_yaml_rule(updater):
    """Test generating rule YAML."""
    context = "Add a rule to check NPI format"
    yaml_output = updater._generate_config_yaml(context, "rule", "")
    
    assert yaml_output
    assert "id:" in yaml_output
    assert "type:" in yaml_output
    assert "severity:" in yaml_output
    assert "message:" in yaml_output


def test_clean_llm_response_removes_markdown(updater):
    """Test cleaning markdown code blocks from LLM response."""
    response = """```yaml
- id: 'TEST-001'
  type: 'regex'
  severity: 'error'
  message: 'Test'
```"""
    
    cleaned = updater._clean_llm_response(response)
    assert "```" not in cleaned
    assert "id: 'TEST-001'" in cleaned


# ── Tests: YAML Validation ────────────────────────────────────────────────────

def test_validate_rule_structure_valid(updater):
    """Test validating valid rule structure."""
    yaml_str = """- id: 'TEST-001'
  type: 'regex'
  target: 'ISA'
  pattern: '^[0-9]+$'
  severity: 'error'
  message: 'Test validation'"""
    
    import yaml
    parsed = yaml.safe_load(yaml_str)
    errors = updater._validate_rule_structure(parsed, [])
    assert len(errors) == 0


def test_validate_rule_structure_missing_id(updater):
    """Test validation catches missing ID."""
    yaml_str = """- type: 'regex'
  severity: 'error'
  message: 'Test'"""
    
    import yaml
    parsed = yaml.safe_load(yaml_str)
    errors = updater._validate_rule_structure(parsed, [])
    assert any("missing required field: 'id'" in err for err in errors)


def test_validate_rule_structure_duplicate_id(updater):
    """Test validation catches duplicate IDs."""
    yaml_str = """- id: 'EXISTING-001'
  type: 'regex'
  severity: 'error'
  message: 'Test'"""
    
    import yaml
    parsed = yaml.safe_load(yaml_str)
    errors = updater._validate_rule_structure(parsed, ['EXISTING-001'])
    assert any("already exists" in err for err in errors)


def test_validate_rule_structure_invalid_severity(updater):
    """Test validation catches invalid severity."""
    yaml_str = """- id: 'TEST-001'
  type: 'regex'
  severity: 'critical'
  message: 'Test'"""
    
    import yaml
    parsed = yaml.safe_load(yaml_str)
    errors = updater._validate_rule_structure(parsed, [])
    assert any("Invalid severity" in err for err in errors)


def test_validate_code_set_structure_valid(updater):
    """Test validating valid code set structure."""
    yaml_str = """code_set_id: 'unique_test_codes_999'
description: 'Test codes'
codes:
  - 'A'
  - 'B'"""
    
    import yaml
    parsed = yaml.safe_load(yaml_str)
    errors = updater._validate_code_set_structure(parsed, [])
    assert len(errors) == 0


def test_validate_code_set_structure_missing_fields(updater):
    """Test validation catches missing fields."""
    yaml_str = """codes:
  - 'A'
  - 'B'"""
    
    import yaml
    parsed = yaml.safe_load(yaml_str)
    errors = updater._validate_code_set_structure(parsed, [])
    assert any("missing required field" in err for err in errors)


# ── Tests: ID Extraction ──────────────────────────────────────────────────────

def test_extract_existing_ids_rules(updater):
    """Test extracting IDs from rules file."""
    content = """rules:
  - id: 'RULE-001'
    type: 'regex'
  - id: 'RULE-002'
    type: 'code_set'"""
    
    ids = updater._extract_existing_ids(content, "rule")
    assert 'RULE-001' in ids
    assert 'RULE-002' in ids


def test_extract_existing_ids_code_set(updater):
    """Test extracting IDs from code set file."""
    content = """code_set_id: 'my_codes'
description: 'Test'
codes:
  - 'A'"""
    
    ids = updater._extract_existing_ids(content, "code_set")
    assert 'my_codes' in ids


# ── Tests: Full Workflow ──────────────────────────────────────────────────────

def test_add_custom_config_success(updater):
    """Test successful config addition."""
    context = "Add a rule to validate NPI format"
    result = updater.add_custom_config(context, config_type="rule")
    
    assert isinstance(result, ConfigUpdateResult)
    assert result.config_type == "rule"
    assert result.target_file
    assert result.generated_yaml


def test_add_custom_config_invalid_type(updater):
    """Test handling invalid config type."""
    result = updater.add_custom_config("test", config_type="invalid")
    
    assert not result.success
    assert "Invalid config_type" in result.validation_errors[0]


def test_add_custom_config_dry_run(updater, temp_config_dir):
    """Test dry run mode doesn't modify files."""
    rules_file = temp_config_dir / 'rules' / 'rules_core.yaml'
    original_content = rules_file.read_text()
    
    result = updater.add_custom_config(
        "Add a test rule",
        config_type="rule",
        target_file="rules_core.yaml"
    )
    
    # File should not be modified in dry run mode
    assert rules_file.read_text() == original_content


def test_preview_config(updater):
    """Test preview functionality."""
    context = "Add a rule to check ISA segment"
    preview = updater.preview_config(context, config_type="rule")
    
    assert preview
    assert isinstance(preview, str)


# ── Tests: Error Handling ─────────────────────────────────────────────────────

def test_handle_llm_failure(temp_config_dir):
    """Test handling LLM failures gracefully."""
    def failing_llm(prompt: str) -> str:
        raise Exception("LLM API error")
    
    updater = LLMConfigUpdater(
        llm=failing_llm,
        config_dir=temp_config_dir,
        dry_run=True
    )
    
    result = updater.add_custom_config("test", config_type="rule")
    
    # Should return error result, not raise exception
    assert not result.success
    assert result.validation_errors


def test_handle_invalid_yaml_from_llm(temp_config_dir):
    """Test handling invalid YAML from LLM."""
    def bad_yaml_llm(prompt: str) -> str:
        if "available files" in prompt.lower():
            return "rules_core.yaml"
        elif "determine the configuration type" in prompt.lower():
            return "rule"
        else:
            return "this is not valid yaml: [[["

    updater = LLMConfigUpdater(
        llm=bad_yaml_llm,
        config_dir=temp_config_dir,
        dry_run=True
    )

    result = updater.add_custom_config("test", config_type="rule")

    assert not result.success
    assert any("Invalid YAML syntax" in err for err in result.validation_errors)


# ── Tests: Backup Creation ────────────────────────────────────────────────────

def test_create_backup(updater, temp_config_dir):
    """Test backup file creation."""
    test_file = temp_config_dir / 'rules' / 'test.yaml'
    test_file.write_text("original content")
    
    backup_path = updater._create_backup(test_file)
    
    assert Path(backup_path).exists()
    assert "backup" in backup_path
    assert Path(backup_path).read_text() == "original content"


# ── Tests: Convenience Function ───────────────────────────────────────────────

def test_convenience_function():
    """Test the convenience function."""
    from validedi.llm import add_custom_config
    
    mock_llm = MockLLM()
    result = add_custom_config(
        context="Add a test rule",
        llm=mock_llm,
        config_type="rule",
        dry_run=True
    )
    
    assert isinstance(result, ConfigUpdateResult)


# ── Run Tests ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
