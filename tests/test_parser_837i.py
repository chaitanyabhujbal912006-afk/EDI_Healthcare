"""
837I parser unit tests
"""
from app.parser.x12_parser import parse_x12
from app.services.summaries import build_837i_summary


SAMPLE_837I = (
    "ISA*00*          *00*          *ZZ*HOSPITAL1      *ZZ*PAYER1         *230101*1200*^*00501*000000001*0*P*:~"
    "GS*HC*HOSPITAL1*PAYER1*20230101*1200*1*X*005010X223A2~"
    "ST*837*0001*005010X223A2~"
    "BHT*0019*00*INV1001*20230101*1200*CH~"
    "NM1*41*2*HOSPITAL BILLING*****46*123456789~"
    "NM1*40*2*INSURANCE CO*****46*987654321~"
    "HL*1**20*1~"
    "NM1*85*2*ST MARY HOSPITAL*****XX*1992837465~"
    "CLM*INST001*1250.00***11:A:1*Y*A*Y*Y~"
    "DTP*434*RD8*20230101-20230105~"
    "SV2*0250**500.00*UN*1~"
    "SV2*0270**750.00*UN*3~"
    "SE*12*0001~GE*1*1~IEA*1*000000001~"
)


def test_parse_basic_837i():
    parsed = parse_x12(SAMPLE_837I)
    assert parsed.transaction_type == "837I"
    assert parsed.envelope.sender_id == "HOSPITAL1"
    assert parsed.envelope.receiver_id == "PAYER1"
    assert len(parsed.segments) == 15


def test_build_837i_summary():
    parsed = parse_x12(SAMPLE_837I)
    summary = build_837i_summary(parsed.segments)
    assert len(summary) == 1
    claim = summary[0]
    assert claim["claim_id"] == "INST001"
    assert claim["total_billed"] == 1250.00
    assert len(claim["revenue_lines"]) == 2
    assert claim["revenue_lines"][0]["revenue_code"] == "0250"
    assert claim["revenue_lines"][0]["charge_amount"] == 500.00
    assert claim["revenue_lines"][1]["revenue_code"] == "0270"
    assert claim["revenue_lines"][1]["charge_amount"] == 750.00
