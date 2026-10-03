"""
Locust load test for EdiPro Healthcare EDI Gateway.
Uploads sample EDI files (837P, 835) to /api/upload at targeted concurrency/rate.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

from locust import HttpUser, between, task

ROOT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_837P = ROOT_DIR / "sample_837p.edi"
SAMPLE_835 = ROOT_DIR / "sample_835.edi"

API_KEY = os.getenv("EDI_API_KEY", "loadtest-admin-key")


class EdiUploadUser(HttpUser):
    # Pacing to achieve ~20 RPS when run with 20 concurrent users
    wait_time = between(0.8, 1.2)

    def on_start(self) -> None:
        self.headers = {"X-API-Key": API_KEY}
        self.samples: list[tuple[str, bytes]] = []

        if SAMPLE_837P.exists():
            self.samples.append(("sample_837p.edi", SAMPLE_837P.read_bytes()))
        if SAMPLE_835.exists():
            self.samples.append(("sample_835.edi", SAMPLE_835.read_bytes()))

        if not self.samples:
            # Fallback synthetic 837P if files not found
            synthetic = (
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
            self.samples.append(("sample_synthetic.edi", synthetic.encode("utf-8")))

    @task(8)
    def upload_edi_file(self) -> None:
        filename, content = random.choice(self.samples)
        files = {"file": (filename, content, "application/octet-stream")}
        self.client.post("/api/upload", headers=self.headers, files=files, name="/api/upload")

    @task(2)
    def check_readiness(self) -> None:
        self.client.get("/api/ready", name="/api/ready")
