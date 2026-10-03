"""
Automated browser E2E test suite using pytest-playwright.

Covers:
1. Sign in with wrong key (error shown) and right key (redirects to dashboard).
2. Upload both sample_835.edi and sample_837p.edi.
3. Verify 835 remittance and 837 claims pages render expected claim details.
4. Upload file with XSS payload <img src=x onerror=window.__xss=1> and assert window.__xss is undefined.
5. Stop backend mid-session and assert UI shows failure, never 'Valid'.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
import pytest
from playwright.sync_api import Page, expect

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_835_PATH = REPO_ROOT / "sample_835.edi"
SAMPLE_837P_PATH = REPO_ROOT / "sample_837p.edi"


def test_auth_login_flow(page: Page, live_server: str):
    """Sign in with wrong key (error shown) and right key (redirects)."""
    login_url = f"{live_server}/stitch/index.html"
    page.goto(login_url)

    # 1. Test wrong API key
    page.fill("#password", "completely-wrong-api-key")
    page.click("#signin-btn")

    # Error banner should become visible with message
    error_banner = page.locator("#login-global-error")
    expect(error_banner).to_be_visible(timeout=5000)
    assert "Invalid API key" in error_banner.inner_text() or "error" in error_banner.inner_text().lower()

    # 2. Test right API key
    page.fill("#password", "secret-e2e-key")
    page.click("#signin-btn")

    # Should redirect to dashboard
    page.wait_for_url("**/dashboard_sleek/code.html", timeout=7000)
    expect(page.locator(".brand-name")).to_contain_text("EdiPro")


def test_upload_samples_and_verify_pages(page: Page, live_server: str):
    """Sign in, upload sample_835.edi and sample_837p.edi, then verify 835 and 837 pages."""
    login_url = f"{live_server}/stitch/index.html"
    page.goto(login_url)
    page.fill("#password", "secret-e2e-key")
    page.click("#signin-btn")
    page.wait_for_url("**/dashboard_sleek/code.html", timeout=7000)

    # Upload sample_835.edi
    file_input = page.locator("#file-upload")
    file_input.set_input_files(str(SAMPLE_835_PATH))
    page.wait_for_timeout(1000)

    # Upload sample_837p.edi
    file_input.set_input_files(str(SAMPLE_837P_PATH))
    page.wait_for_timeout(1500)

    # Verify 835 Remittance page
    page.goto(f"{live_server}/stitch/835_remittance_sleek/code.html")
    page.wait_for_timeout(1000)
    page_content_835 = page.content()
    assert "CLAIM001" in page_content_835
    assert "500.00" in page_content_835
    assert "450.00" in page_content_835

    # Verify 837 Claims page
    page.goto(f"{live_server}/stitch/837_claims_view/code.html")
    page.wait_for_timeout(1000)
    page_content_837 = page.content()
    assert "CLAIM001" in page_content_837
    assert "500.00" in page_content_837


def test_xss_prevention_in_nm1(page: Page, live_server: str, tmp_path: Path):
    """Upload a file containing <img src=x onerror=window.__xss=1> and assert window.__xss is undefined."""
    login_url = f"{live_server}/stitch/index.html"
    page.goto(login_url)
    page.fill("#password", "secret-e2e-key")
    page.click("#signin-btn")
    page.wait_for_url("**/dashboard_sleek/code.html", timeout=7000)

    # Create synthetic EDI with XSS vector in NM1
    xss_edi = (
        "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *260824*1030*U*00501*000000001*0*P*>~\n"
        "GS*HC*SUBMITTER1*RECEIVER1*20260824*1030*1*X*005010X222A1~\n"
        "ST*837*0001*005010X222A1~\n"
        "BHT*0019*00*244579*20260824*1030*CH~\n"
        "HL*1**20*1~\n"
        "NM1*85*2*METRO HOSPITAL*****XX*1992837465~\n"
        "HL*2*1*22*0~\n"
        "NM1*IL*1*<img src=x onerror=window.__xss=1>*JOHN****MI*SUB12345~\n"
        "CLM*CLM001*100.00***11:B:1*Y*A*Y*Y~\n"
        "LX*1~\n"
        "SV1*HC:99214*100.00*UN*1***1~\n"
        "SE*11*0001~GE*1*1~IEA*1*000000001~"
    )
    xss_file = tmp_path / "xss_payload.edi"
    xss_file.write_text(xss_edi, encoding="utf-8")

    file_input = page.locator("#file-upload")
    file_input.set_input_files(str(xss_file))
    page.wait_for_timeout(1500)

    # Check whether the injected JavaScript was executed
    is_xss_defined = page.evaluate("() => typeof window.__xss !== 'undefined'")
    assert not is_xss_defined, "XSS execution detected! window.__xss was defined."


def test_stop_backend_shows_failure_never_valid(page: Page, tmp_path: Path, uvicorn_launcher):
    """Stop the backend mid-session and assert the UI shows a failure, never 'Valid'."""
    proc, url = uvicorn_launcher(api_key="backend-stop-key")
    try:
        login_url = f"{url}/stitch/index.html"
        page.goto(login_url)
        page.fill("#password", "backend-stop-key")
        page.click("#signin-btn")
        page.wait_for_url("**/dashboard_sleek/code.html", timeout=7000)

        # Confirm backend is online initially
        page.wait_for_timeout(500)

        # Stop backend server abruptly mid-session
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

        # Attempt to upload a file while backend is dead
        test_file = tmp_path / "offline_claim.edi"
        test_file.write_text(SAMPLE_837P_PATH.read_text(encoding="utf-8"), encoding="utf-8")

        file_input = page.locator("#file-upload")
        file_input.set_input_files(str(test_file))
        page.wait_for_timeout(2000)

        # Check UI notifications or audit card
        recent_audits = page.locator("#recent-audits")
        text_content = recent_audits.inner_text()

        # Must NEVER state "Valid"
        assert "Valid" not in text_content or "Invalid" in text_content, "UI displayed 'Valid' even though backend was offline!"

        # A failure toast or offline indicator must be triggered
        toast = page.locator("#toast-container, .toast")
        toast_text = toast.inner_text() if toast.count() > 0 else ""
        assert "Upload Failed" in toast_text or "error" in toast_text.lower() or "connection" in toast_text.lower()
    finally:
        try:
            proc.kill()
        except Exception:
            pass
