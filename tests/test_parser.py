"""
Tests for parser module.
"""

import pytest
from validedi import parse
from validedi.utils.exceptions import EDIParseError


def test_parse_835_basic():
    """Test parsing a basic 835 transaction."""
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
    
    result = parse(raw)
    
    assert result.envelope.transaction_type == '835'
    assert result.envelope.sender_id == 'SENDER'
    assert result.envelope.receiver_id == 'RECEIVER'
    assert len(result.loops) > 0


def test_parse_837p_basic():
    """Test parsing a basic 837P transaction."""
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
        "DMG*D8*19800101*M~"
        "CLM*CLAIM123*100.00***11:B:1*Y*A*Y*Y~"
        "SE*12*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )
    
    result = parse(raw)
    
    assert result.envelope.transaction_type == '837p'
    assert len(result.loops) > 0
