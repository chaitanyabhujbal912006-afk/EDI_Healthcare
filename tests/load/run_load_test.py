"""
Execution harness for EdiPro load testing.
Runs an upload benchmark at 20 requests/second for 60 seconds.
Measures and prints p50, p95, p99 latencies, error rate, throughput, and host specs.
"""
from __future__ import annotations

import asyncio
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any

import httpx
import psutil

ROOT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_837P = ROOT_DIR / "sample_837p.edi"
SAMPLE_835 = ROOT_DIR / "sample_835.edi"

TARGET_URL = os.getenv("TARGET_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("EDI_API_KEY", "prod-load-test-key")
TARGET_RPS = 20
DURATION_SECONDS = 60


def get_host_specs() -> dict[str, Any]:
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "processor": platform.processor(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "python_version": platform.python_version(),
    }


async def send_single_upload(
    client: httpx.AsyncClient, file_name: str, file_bytes: bytes
) -> tuple[bool, float, int]:
    """Send an upload request and return (success, latency_ms, status_code)."""
    start = time.perf_counter()
    try:
        res = await client.post(
            f"{TARGET_URL}/api/upload",
            headers={"X-API-Key": API_KEY},
            files={"file": (file_name, file_bytes, "application/octet-stream")},
            timeout=30.0,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        success = res.status_code == 200
        return success, latency_ms, res.status_code
    except Exception:  # noqa: BLE001
        latency_ms = (time.perf_counter() - start) * 1000
        return False, latency_ms, 599


async def run_benchmark(target_rps: int = TARGET_RPS, duration_sec: int = DURATION_SECONDS) -> dict[str, Any]:
    print("\n=======================================================")
    print("Starting EdiPro Load Benchmark")
    print(f"Target: {TARGET_URL} | Rate: {target_rps} RPS | Duration: {duration_sec}s")
    print("=======================================================\n")

    # Prepare sample payloads
    samples = []
    if SAMPLE_837P.exists():
        samples.append(("sample_837p.edi", SAMPLE_837P.read_bytes()))
    if SAMPLE_835.exists():
        samples.append(("sample_835.edi", SAMPLE_835.read_bytes()))

    if not samples:
        synthetic = "ISA*00*          *00*          *ZZ*SUBMITTER1     *ZZ*RECEIVER1      *260824*1030*U*00501*000000001*0*P*>~GS*HC*SUBMITTER1*RECEIVER1*20260824*1030*1*X*005010X222A1~ST*837*0001*005010X222A1~SE*3*0001~GE*1*1~IEA*1*000000001~"
        samples.append(("sample_synth.edi", synthetic.encode("utf-8")))

    latencies_ms: list[float] = []
    status_codes: dict[int, int] = {}
    success_count = 0
    failure_count = 0

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(limits=limits) as client:
        start_benchmark = time.perf_counter()
        import random

        interval = 1.0 / target_rps
        tasks: list[asyncio.Task] = []

        total_scheduled = 0
        end_time = start_benchmark + duration_sec

        while time.perf_counter() < end_time:
            tick_start = time.perf_counter()
            name, content = random.choice(samples)
            t = asyncio.create_task(send_single_upload(client, name, content))
            tasks.append(t)
            total_scheduled += 1

            # Pacing
            elapsed = time.perf_counter() - tick_start
            sleep_needed = interval - elapsed
            if sleep_needed > 0:
                await asyncio.sleep(sleep_needed)

            # Print status update every 10 seconds
            curr_elapsed = time.perf_counter() - start_benchmark
            if total_scheduled % (target_rps * 10) == 0:
                print(f"[{curr_elapsed:.1f}s / {duration_sec}s] Dispatched {total_scheduled} requests...")

        print("\nAwaiting completion of remaining in-flight requests...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

    actual_duration = time.perf_counter() - start_benchmark

    for r in results:
        if isinstance(r, Exception):
            failure_count += 1
            status_codes[599] = status_codes.get(599, 0) + 1
            continue
        success, lat, code = r
        latencies_ms.append(lat)
        status_codes[code] = status_codes.get(code, 0) + 1
        if success:
            success_count += 1
        else:
            failure_count += 1

    total_requests = len(results)
    error_rate = (failure_count / total_requests * 100) if total_requests else 0.0
    actual_rps = (total_requests / actual_duration) if actual_duration else 0.0

    if latencies_ms:
        latencies_sorted = sorted(latencies_ms)
        p50 = statistics.median(latencies_sorted)
        # Quantiles
        n = len(latencies_sorted)
        p95 = latencies_sorted[int(0.95 * n)] if n > 1 else latencies_sorted[0]
        p99 = latencies_sorted[int(0.99 * n)] if n > 1 else latencies_sorted[0]
        avg_lat = statistics.mean(latencies_sorted)
        min_lat = min(latencies_sorted)
        max_lat = max(latencies_sorted)
    else:
        p50 = p95 = p99 = avg_lat = min_lat = max_lat = 0.0

    summary = {
        "target_url": TARGET_URL,
        "target_rps": target_rps,
        "duration_seconds": round(actual_duration, 2),
        "total_requests": total_requests,
        "success_count": success_count,
        "failure_count": failure_count,
        "error_rate_pct": round(error_rate, 2),
        "actual_rps": round(actual_rps, 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "latency_p99_ms": round(p99, 2),
        "latency_avg_ms": round(avg_lat, 2),
        "latency_min_ms": round(min_lat, 2),
        "latency_max_ms": round(max_lat, 2),
        "status_distribution": status_codes,
        "host_specs": get_host_specs(),
    }

    print("\n---------------- Benchmark Results ----------------")
    print(f"Total Requests : {total_requests}")
    print(f"Throughput     : {summary['actual_rps']} req/s")
    print(f"Success / Fail : {success_count} / {failure_count}")
    print(f"Error Rate     : {summary['error_rate_pct']}%")
    print(f"p50 Latency    : {summary['latency_p50_ms']} ms")
    print(f"p95 Latency    : {summary['latency_p95_ms']} ms")
    print(f"p99 Latency    : {summary['latency_p99_ms']} ms")
    print(f"Avg Latency    : {summary['latency_avg_ms']} ms")
    print(f"Min / Max      : {summary['latency_min_ms']} ms / {summary['latency_max_ms']} ms")
    print(f"Status Codes   : {status_codes}")
    print("---------------------------------------------------\n")

    return summary


if __name__ == "__main__":
    asyncio.run(run_benchmark())
