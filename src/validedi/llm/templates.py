"""
Rule-based template rendering for EDI explanations.
Fallback when no LLM is provided.
"""

import textwrap
from typing import Any


def render_rule_based_report(edi_result: Any, val_result: Any) -> str:
    """
    Generate a structured report using rule-based templates.
    
    Args:
        edi_result: Parsed EDI result (ParsedEDI object)
        val_result: Validation result (ValidationResult object)
        
    Returns:
        Formatted report string
    """
    tx = edi_result.envelope.transaction_type
    env = edi_result.envelope
    
    tx_descriptions = {
        "837P": "Professional Claim (837P) — outpatient/office services billed with CPT codes.",
        "837I": "Institutional Claim (837I) — inpatient/facility services billed with revenue codes.",
        "835": "Remittance Advice (835) — payer explanation of claim payments and adjustments.",
        "834": "Benefit Enrollment (834) — member insurance enrollment/change/termination.",
    }

    lines = [
        "=" * 70,
        f"  EDI REPORT — {tx}",
        "=" * 70,
        "",
        "OVERVIEW",
        "--------",
        tx_descriptions.get(tx, f"X12 {tx} transaction."),
        "",
        f"  Sender:    {env.sender_id}",
        f"  Receiver:  {env.receiver_id}",
        f"  Date:      {env.interchange_date}",
        f"  Time:      {env.interchange_time}",
        f"  Version:   {env.version}",
        f"  Control #: {env.st_control_number}",
        "",
        "STRUCTURE",
        "---------",
        f"  Total Loops:    {len(edi_result.loops)}",
        f"  Total Segments: {sum(len(loop.segments) for loop in edi_result.loops)}",
        "",
    ]

    # Validation status
    lines += ["", "VALIDATION STATUS", "-----------------"]
    
    if val_result.is_valid:
        lines.append("  ✅ No errors found")
    else:
        lines.append(f"  ❌ Found {val_result.error_count} error(s)")
    
    if val_result.warning_count > 0:
        lines.append(f"  ⚠️  Found {val_result.warning_count} warning(s)")
    
    lines.append("")
    
    for err in val_result.errors:
        icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(err.severity, "  ")
        lines.append(f"  {icon} [{err.code}] {err.segment}: {err.message}")
        lines.append("")

    lines += ["=" * 70, "  END OF REPORT", "=" * 70]
    return "\n".join(lines)
