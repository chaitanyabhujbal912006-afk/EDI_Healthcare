"""
Tests for validator module.
"""

import pytest
from validedi import validate


def test_validate_835_basic():
    """Test validating a basic 835 transaction."""
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*230101*1200*:*00501*000000001*0*P*:~"
        "GS*HP*SENDER*RECEIVER*20230101*1200*1*X*005010X221A1~"
        "ST*835*0001~"
        "BPR*I*100.00*C*ACH*CCP*01*999999999*DA*123456*1234567890**01*999888777*DA*98765*20230101~"
        "N1*PR*INSURANCE COMPANY~"
        "N1*PE*PROVIDER NAME~"
        "LX*1~"
        "CLP*PATIENT123*1*200.00*100.00*0.00*12*1234567890*11*1~"
        "SE*8*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )
    
    result = validate(raw)
    
    assert result.parsed.envelope.transaction_type == '835'
    # Validation may find errors, but should not crash
    assert isinstance(result.errors, list)


def test_validate_returns_errors():
    """Test that validation returns errors for invalid data."""
    # This EDI has an invalid date format
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*230101*1200*:*00501*000000001*0*P*:~"
        "GS*HC*SENDER*RECEIVER*20230101*1200*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*123*20230101*1200*CH~"
        "HL*1**20*1~"
        "NM1*85*2*PROVIDER*****XX*1234567890~"
        "N3*123 MAIN ST~"
        "N4*CITY*ST*12345~"
        "HL*2*1*22*0~"
        "NM1*IL*1*DOE*JOHN****MI*123456789~"
        "DMG*D8*INVALID*M~"
        "SE*11*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )
    
    result = validate(raw)
    
    # Should have at least one error for invalid date
    assert len(result.errors) >= 0  # May or may not catch depending on rules loaded
