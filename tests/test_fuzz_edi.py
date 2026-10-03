"""
Fuzz-style testing for EDI parser and API endpoints.

Feeds truncated, oversized-element, wrong-delimiter and BOM-prefixed variants
of every sample and asserts:
- No 500 status code
- A clear validation issue or 4xx HTTP response
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.adapters import validate_edi_content, parse_edi_content
from validedi.engine.validator import validate as validedi_validate


REPO_ROOT = Path(__file__).resolve().parent.parent

# Read root samples
ROOT_835 = (REPO_ROOT / "sample_835.edi").read_text(encoding="utf-8")
ROOT_837P = (REPO_ROOT / "sample_837p.edi").read_text(encoding="utf-8")

# Synthetic 837I and 834 samples
SAMPLE_837I = (
    "ISA*00*          *00*          *ZZ*HOSPITAL1      *ZZ*PAYER1         *230101*1200*^*00501*000000001*0*P*:~\n"
    "GS*HC*HOSPITAL1*PAYER1*20230101*1200*1*X*005010X223A2~\n"
    "ST*837*0001*005010X223A2~\n"
    "BHT*0019*00*INV1001*20230101*1200*CH~\n"
    "NM1*41*2*HOSPITAL BILLING*****46*123456789~\n"
    "NM1*40*2*INSURANCE CO*****46*987654321~\n"
    "HL*1**20*1~\n"
    "NM1*85*2*ST MARY HOSPITAL*****XX*1234567893~\n"
    "CLM*INST001*1250.00***11:A:1*Y*A*Y*Y~\n"
    "DTP*434*RD8*20230101-20230105~\n"
    "SV2*0250**500.00*UN*1~\n"
    "SV2*0270**750.00*UN*3~\n"
    "SE*12*0001~GE*1*1~IEA*1*000000001~"
)

SAMPLE_834 = (
    "ISA*00*          *00*          *ZZ*SPONSOR1       *ZZ*PAYER1         *260824*1200*^*00501*000000003*0*P*:~\n"
    "GS*BE*SPONSOR1*PAYER1*20260824*1200*3*X*005010X220A1~\n"
    "ST*834*0003~\n"
    "BGN*00*12345*20260824*1200****2~\n"
    "N1*P5*SPONSOR COMPANY~\n"
    "INS*Y*18*001*28*A***FT~\n"
    "REF*0F*MEMB1001~\n"
    "NM1*IL*1*DOE*JANE*A***34*123456789~\n"
    "HD*030**IND~\n"
    "DTP*348*D8*20260101~\n"
    "SE*9*0003~GE*1*3~IEA*1*000000003~"
)

SAMPLES = [
    ("sample_835.edi", ROOT_835),
    ("sample_837p.edi", ROOT_837P),
    ("sample_837i.edi", SAMPLE_837I),
    ("sample_834.edi", SAMPLE_834),
]


@pytest.fixture(scope="module")
def client():
    with patch.dict(os.environ, {"EDI_API_KEYS": "fuzz-key:admin"}), TestClient(app) as test_client:
        yield test_client


AUTH_HEADERS = {"X-API-Key": "fuzz-key"}


# ── 1. Truncated Variants ───────────────────────────────────────────────────


@pytest.mark.parametrize("sample_name,sample_text", SAMPLES)
@pytest.mark.parametrize("cut_ratio", [0.05, 0.25, 0.5, 0.75, 0.90])
def test_fuzz_truncated_variants(client: TestClient, sample_name: str, sample_text: str, cut_ratio: float):
    cut_len = min(len(sample_text) - 15, max(5, int(len(sample_text) * cut_ratio)))
    truncated = sample_text[:cut_len]

    # Test /api/upload
    files = {"file": (sample_name, io.BytesIO(truncated.encode("utf-8")), "text/plain")}
    resp_upload = client.post("/api/upload", files=files, headers=AUTH_HEADERS)
    assert resp_upload.status_code != 500, f"500 returned on /api/upload with cut {cut_ratio}"
    assert resp_upload.status_code in {200, 400, 422}
    if resp_upload.status_code == 200:
        val = resp_upload.json()["report"]["validation_result"]
        assert val["valid"] is False
        assert len(val["issues"]) > 0

    # Test /api/parse
    resp_parse = client.post("/api/parse", json={"content": truncated}, headers=AUTH_HEADERS)
    assert resp_parse.status_code != 500, f"500 returned on /api/parse with cut {cut_ratio}"
    assert resp_parse.status_code in {200, 400, 422}
    if resp_parse.status_code == 200:
        val = resp_parse.json()["validation_result"]
        assert val["valid"] is False
        assert len(val["issues"]) > 0

    # Test direct library validate
    res = validate_edi_content(truncated)
    assert res.valid is False
    assert len(res.issues) > 0


# ── 2. Oversized-Element Variants ───────────────────────────────────────────


@pytest.mark.parametrize("sample_name,sample_text", SAMPLES)
@pytest.mark.parametrize("chunk_size", [1500, 5000])
def test_fuzz_oversized_elements(client: TestClient, sample_name: str, sample_text: str, chunk_size: int):
    oversized = "A" * chunk_size
    parts = sample_text.split("~")
    if len(parts) > 2:
        mutated_seg = parts[1] + "*" + oversized
        mutated_text = parts[0] + "~" + mutated_seg + "~" + "~".join(parts[2:])
    else:
        mutated_text = sample_text + "*" + oversized + "~"

    # Test /api/parse
    resp_parse = client.post("/api/parse", json={"content": mutated_text}, headers=AUTH_HEADERS)
    assert resp_parse.status_code != 500
    assert resp_parse.status_code in {200, 400, 422}

    # Test /api/upload
    files = {"file": (sample_name, io.BytesIO(mutated_text.encode("utf-8")), "text/plain")}
    resp_upload = client.post("/api/upload", files=files, headers=AUTH_HEADERS)
    assert resp_upload.status_code != 500
    assert resp_upload.status_code in {200, 400, 422}

    # Direct validation
    res = validate_edi_content(mutated_text)
    assert isinstance(res.valid, bool)


# ── 3. Wrong-Delimiter Variants ─────────────────────────────────────────────


@pytest.mark.parametrize("sample_name,sample_text", SAMPLES)
@pytest.mark.parametrize("wrong_delim", ["|", "^", ",", "#"])
def test_fuzz_wrong_delimiters(client: TestClient, sample_name: str, sample_text: str, wrong_delim: str):
    # Mutate separators in the message body while keeping ISA prefix
    if "~" in sample_text and len(sample_text) > 106:
        isa_part = sample_text[:106]
        body_part = sample_text[106:].replace("*", wrong_delim)
        mutated = isa_part + body_part
    else:
        mutated = sample_text.replace("*", wrong_delim)

    # Test /api/parse
    resp_parse = client.post("/api/parse", json={"content": mutated}, headers=AUTH_HEADERS)
    assert resp_parse.status_code != 500
    assert resp_parse.status_code in {200, 400, 422}
    if resp_parse.status_code == 200:
        val = resp_parse.json()["validation_result"]
        assert val["valid"] is False
        assert len(val["issues"]) > 0

    # Test /api/upload
    files = {"file": (sample_name, io.BytesIO(mutated.encode("utf-8")), "text/plain")}
    resp_upload = client.post("/api/upload", files=files, headers=AUTH_HEADERS)
    assert resp_upload.status_code != 500
    assert resp_upload.status_code in {200, 400, 422}
    if resp_upload.status_code == 200:
        val = resp_upload.json()["report"]["validation_result"]
        assert val["valid"] is False
        assert len(val["issues"]) > 0

    # Direct validation check
    res = validate_edi_content(mutated)
    assert res.valid is False
    assert len(res.issues) > 0


# ── 4. BOM-Prefixed Variants ────────────────────────────────────────────────


@pytest.mark.parametrize("sample_name,sample_text", SAMPLES)
def test_fuzz_bom_prefixed(client: TestClient, sample_name: str, sample_text: str):
    # 1. UTF-8 string with BOM \ufeff
    bom_str = "\ufeff" + sample_text

    resp_parse = client.post("/api/parse", json={"content": bom_str}, headers=AUTH_HEADERS)
    assert resp_parse.status_code != 500
    assert resp_parse.status_code in {200, 400, 422}

    # 2. Raw bytes with UTF-8 BOM
    bom_bytes = b"\xef\xbb\xbf" + sample_text.encode("utf-8")
    files = {"file": (sample_name, io.BytesIO(bom_bytes), "text/plain")}
    resp_upload = client.post("/api/upload", files=files, headers=AUTH_HEADERS)
    assert resp_upload.status_code != 500
    assert resp_upload.status_code in {200, 400, 422}

    # 3. Direct library check
    res = validate_edi_content(bom_str)
    assert isinstance(res.valid, bool)
