from app.parser.x12_parser import parse_x12
from app.validation.rules import validate


def test_validate_837p_billing_provider_npi_valid():
    edi = (
        "ISA*00*          *00*          *ZZ*SENDER123      *ZZ*RECEIVER456    *230101*1200*^*00501*000000001*0*P*:~"
        "GS*HC*SENDER123*RECEIVER456*20230101*1200*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*123*20230101*1200*CH~"
        "NM1*85*2*GENERAL HOSPITAL*****XX*1234567890~"
        "CLM*CLM001*150.00***11:B:1*Y*A*Y*I~"
        "SE*7*0001~GE*1*1~IEA*1*000000001~"
    )
    parsed = parse_x12(edi)
    result = validate(parsed)
    codes = [i.code for i in result.issues]
    assert "BILLING_NPI_REQUIRED" not in codes


def test_validate_837p_billing_provider_missing_npi():
    edi = (
        "ISA*00*          *00*          *ZZ*SENDER123      *ZZ*RECEIVER456    *230101*1200*^*00501*000000001*0*P*:~"
        "GS*HC*SENDER123*RECEIVER456*20230101*1200*1*X*005010X222A1~"
        "ST*837*0001*005010X222A1~"
        "BHT*0019*00*123*20230101*1200*CH~"
        "NM1*85*2*GENERAL HOSPITAL~"  # Missing XX and NPI
        "CLM*CLM001*150.00***11:B:1*Y*A*Y*I~"
        "SE*7*0001~GE*1*1~IEA*1*000000001~"
    )
    parsed = parse_x12(edi)
    result = validate(parsed)
    codes = [i.code for i in result.issues]
    assert "BILLING_NPI_REQUIRED" in codes
