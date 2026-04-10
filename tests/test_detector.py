"""
Tests for detector module.
"""

import pytest
from validedi.engine.detector import detect, DelimiterSet
from validedi.utils.exceptions import EDIParseError, UnsupportedTransactionError


def test_detect_standard_delimiters():
    """Test detection with standard delimiters."""
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*230101*1200*:*00501*000000001*0*P*:~"
        "GS*HP*SENDER*RECEIVER*20230101*1200*1*X*005010X221A1~"
        "ST*835*0001~"
        "SE*1*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )
    
    result = detect(raw)
    
    assert result.element_sep == '*'
    assert result.segment_sep == '~'
    assert result.sub_sep == ':'
    assert result.transaction_type == '835'


def test_detect_truncated_isa():
    """Test that truncated ISA raises EDIParseError."""
    raw = "ISA*00*"
    
    with pytest.raises(EDIParseError) as exc_info:
        detect(raw)
    
    assert 'too short' in str(exc_info.value).lower()


def test_detect_unsupported_transaction():
    """Test that unsupported transaction type raises UnsupportedTransactionError."""
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*230101*1200*:*00501*000000001*0*P*:~"
        "GS*XX*SENDER*RECEIVER*20230101*1200*1*X*005010~"
        "ST*999*0001~"
    )
    
    with pytest.raises(UnsupportedTransactionError):
        detect(raw)
