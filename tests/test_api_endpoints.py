"""
Unit tests for FastAPI REST API endpoints in EdiPro backend.
"""
from __future__ import annotations

import io
import zipfile

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

SAMPLE_837P = (
    "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *260824*1030*U*00501*000000001*0*P*>~\n"
    "GS*HC*SUBMITTER1*RECEIVER1*20260824*1030*1*X*005010X222A1~\n"
    "ST*837*0001*005010X222A1~\n"
    "BHT*0019*00*244579*20260824*1030*CH~\n"
    "NM1*41*2*PREMIUM HEALTH INC*****46*1234567890~\n"
    "PER*IC*EDI DEPT*TE*8005551212~\n"
    "NM1*40*2*HEALTHPAY INC*****46*9876543210~\n"
    "HL*1**20*1~\n"
    "PRV*BI*PXC*207Q00000X~\n"
    "NM1*85*2*METRO MEDICAL CENTER*****XX*1992837465~\n"
    "N3*100 MAIN STREET~\n"
    "N4*METROPOLIS*NY*10001~\n"
    "REF*EI*123456789~\n"
    "HL*2*1*22*0~\n"
    "SBR*P*18*GRP12345******CI~\n"
    "NM1*IL*1*SMITH*JOHN*M***MI*SUB12345678~\n"
    "N3*456 ELM AVE~\n"
    "N4*METROPOLIS*NY*10001~\n"
    "DMG*D8*19800512*M~\n"
    "NM1*PR*2*HEALTHPAY INC*****PI*98765~\n"
    "CLM*CLM-99401*1250.00***11:B:1*Y*A*Y*Y~\n"
    "HI*BK:99214*BF:78009~\n"
    "LX*1~\n"
    "SV1*HC:99214*1250.00*UN*1***1~\n"
    "DTP*472*D8*20260820~\n"
    "SE*25*0001~\n"
    "GE*1*1~\n"
    "IEA*1*000000001~"
)

SAMPLE_835 = (
    "ISA*00*          *00*          *ZZ*PAYER1         *ZZ*PROVIDER1      *260824*1100*U*00501*000000002*0*P*>~\n"
    "GS*HP*PAYER1*PROVIDER1*20260824*1100*2*X*005010X221A1~\n"
    "ST*835*0002~\n"
    "BPR*I*1250.00*C*ACH*CTX*01*999999999*DA*111111*1999999999**01*999999999*DA*222222*20260824~\n"
    "TRN*1*123456789*1999999999~\n"
    "N1*PR*PAYER ONE~\n"
    "N1*PE*METRO MEDICAL CENTER*XX*1992837465~\n"
    "CLP*CLM-99401*1*1250.00*1000.00*250.00*MC*12345678901*11:B:1*1~\n"
    "CAS*CO*45*250.00~\n"
    "SVC*HC:99214*1250.00*1000.00~\n"
    "DTM*472*20260820~\n"
    "SE*10*0002~\n"
    "GE*1*2~\n"
    "IEA*1*000000002~"
)

SAMPLE_834 = (
    "ISA*00*          *00*          *ZZ*SPONSOR1       *ZZ*PAYER1         *260824*1200*U*00501*000000003*0*P*>~\n"
    "GS*BE*SPONSOR1*PAYER1*20260824*1200*3*X*005010X220A1~\n"
    "ST*834*0003~\n"
    "BGN*00*12345*20260824*1200****2~\n"
    "N1*P5*SPONSOR COMPANY~\n"
    "INS*Y*18*001*28*A***FT~\n"
    "REF*0F*MEMB1001~\n"
    "NM1*IL*1*DOE*JANE*A***34*123456789~\n"
    "HD*030**IND~\n"
    "DTP*348*D8*20260101~\n"
    "SE*9*0003~\n"
    "GE*1*3~\n"
    "IEA*1*000000003~"
)


def test_health_check() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stats_overview() -> None:
    response = client.get("/api/stats/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["total_built_in_rules"] >= 64


def test_parse_raw_edi() -> None:
    response = client.post("/api/parse", json={"content": SAMPLE_837P})
    assert response.status_code == 200
    data = response.json()
    assert "parse_result" in data
    assert "validation_result" in data
    assert data["parse_result"]["transaction_type"] == "837P"


def test_upload_file_edi() -> None:
    file_bytes = SAMPLE_835.encode("utf-8")
    response = client.post(
        "/api/upload",
        files={"file": ("sample_835.edi", file_bytes, "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["filename"] == "sample_835.edi"
    assert payload["report"]["parse_result"]["transaction_type"] == "835"
    assert len(payload["remittance_summary"]) > 0


def test_batch_upload_zip() -> None:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("claim1.edi", SAMPLE_837P)
        zf.writestr("remit1.edi", SAMPLE_835)

    zip_bytes = zip_buffer.getvalue()
    response = client.post(
        "/api/batch",
        files={"file": ("batch.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 200
    batch_res = response.json()
    assert batch_res["total_files"] == 2
    assert len(batch_res["reports"]) == 2


def test_reconcile_835_837() -> None:
    payload = {"edi_837": SAMPLE_837P, "edi_835": SAMPLE_835}
    response = client.post("/api/reconcile/835-837", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert "rows" in res
    assert "matched" in res
    assert len(res["rows"]) >= 1
    assert res["rows"][0]["claim_id"] == "CLM-99401"
    assert res["rows"][0]["835_paid"] == 1000.00


def test_delta_834() -> None:
    payload = {"old_834": SAMPLE_834, "new_834": SAMPLE_834}
    response = client.post("/api/delta/834", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert "added" in res
    assert "terminated" in res
    assert "changed" in res


def test_eligibility_check() -> None:
    payload = {"edi_834": SAMPLE_834, "edi_837": SAMPLE_837P}
    response = client.post("/api/eligibility/834-837", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert "total_claims_with_member_ref" in res
    assert "ineligible_claims" in res


def test_export_json() -> None:
    payload = {"status": "success", "count": 42}
    response = client.post("/api/export/json", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"


def test_export_members_csv() -> None:
    payload = {"rows": [{"member_id": "M100", "name": "John Doe", "status": "Active"}]}
    response = client.post("/api/export/members-csv", json=payload)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert b"John Doe" in response.content


def test_export_errors_pdf() -> None:
    payload = {"issues": [{"code": "ERR01", "message": "Missing NPI number"}]}
    response = client.post("/api/export/errors-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_system_stats_overview() -> None:
    response = client.get("/api/stats/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "837P" in data["supported_transactions"]
    assert data["total_built_in_rules"] > 0
    assert "active_rule_categories" in data


def test_export_reconciliation_csv() -> None:
    payload = {
        "rows": [
            {
                "claim_id": "CLM999",
                "837_billed": 500.0,
                "835_billed": 500.0,
                "835_paid": 450.0,
                "variance": 50.0,
            }
        ]
    }
    response = client.post("/api/export/reconciliation-csv", json=payload)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert b"CLM999" in response.content
    assert b"500.0" in response.content


def test_api_version() -> None:
    response = client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "EdiPro Healthcare EDI Gateway"
    assert data["api_version"] == "1.0.0"
    assert data["library"] == "validedi"
    assert "supported_transactions" in data
    assert "837P" in data["supported_transactions"]
    assert "837I" in data["supported_transactions"]


def test_health_detailed() -> None:
    response = client.get("/api/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert data["total_built_in_rules"] > 0
    assert "llm_providers" in data
    assert "837I" in data["supported_transactions"]


def test_export_tsv() -> None:
    payload = {"rows": [{"claim_id": "CLM101", "service": "99213", "paid": "120.00"}]}
    response = client.post("/api/export/members-tsv", json=payload)
    assert response.status_code == 200
    assert "text/tab-separated-values" in response.headers["content-type"]
    assert b"CLM101\t99213\t120.00" in response.content


def test_summary_837i() -> None:
    sample_837i = (
        "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *260824*1030*U*00501*000000001*0*P*>~\n"
        "GS*HC*SUBMITTER1*RECEIVER1*20260824*1030*1*X*005010X223A2~\n"
        "ST*837*0001*005010X223A2~\n"
        "BHT*0019*00*12345*20260824*1030*CH~\n"
        "NM1*41*2*HOSPITAL INC*****46*1234567890~\n"
        "CLM*INST-001*5400.00***11:A:1*Y*A*Y*Y~\n"
        "LX*1~\n"
        "SV2*0110*HC:99214*1500.00*UN*1~\n"
        "LX*2~\n"
        "SV2*0250*HC:99215*3900.00*UN*1~\n"
        "SE*10*0001~\n"
        "GE*1*1~\n"
        "IEA*1*000000001~"
    )
    response = client.post("/api/summary/837i", json={"content": sample_837i})
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_type"] == "837I"
    assert data["claim_count"] == 1
    assert data["total_billed"] == 5400.00
    assert len(data["claims"]) == 1
    assert len(data["claims"][0]["revenue_lines"]) == 2
    assert data["claims"][0]["revenue_lines"][0]["revenue_code"] == "0110"
    assert data["claims"][0]["revenue_lines"][0]["charge_amount"] == 1500.00

