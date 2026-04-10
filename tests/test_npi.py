"""
Tests for NPI Luhn validation.
"""

import pytest
from validedi.handlers.npi import luhn_check


def test_valid_npi():
    """Test that valid NPI passes Luhn check."""
    # Known valid NPI
    assert luhn_check('1234567893') is True


def test_invalid_check_digit():
    """Test that invalid check digit fails."""
    assert luhn_check('1234567890') is False


def test_non_numeric_npi():
    """Test that non-numeric NPI raises ValueError."""
    with pytest.raises(ValueError):
        luhn_check('123456789A')


def test_wrong_length():
    """Test that wrong length NPI raises ValueError."""
    with pytest.raises(ValueError):
        luhn_check('123456789')
    
    with pytest.raises(ValueError):
        luhn_check('12345678901')
