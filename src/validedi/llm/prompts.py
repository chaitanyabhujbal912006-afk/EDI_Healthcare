"""
Prompt templates and builders for LLM explanations.
"""

from typing import Any


def build_explanation_prompt(edi_result: Any, val_result: Any, extracted_data: Any = None) -> str:
    """
    Build a prompt for generating a plain-English EDI explanation.
    
    Args:
        edi_result: Parsed EDI result from parser (ParsedEDI object)
        val_result: Validation result from validator (ValidationResult object)
        extracted_data: Optional extracted business data (claims/payments/enrollments)
        
    Returns:
        Formatted prompt string for LLM
    """
    import json
    
    tx = edi_result.envelope.transaction_type
    env = edi_result.envelope

    # Build validation issues summary
    if val_result.errors:
        issue_lines = [
            f"  [{err.severity.upper()}] {err.code} — {err.segment}: {err.message}"
            for err in val_result.errors[:15]
        ]
        issues_text = "\n".join(issue_lines)
    else:
        issues_text = "  No issues found."

    # Extract key facts from loops
    facts = extract_key_facts_from_loops(tx, edi_result.loops)
    
    # Add extracted business data if provided
    extracted_section = ""
    if extracted_data:
        try:
            extracted_json = json.dumps(extracted_data, indent=2, default=str)
            extracted_section = f"\n\nEXTRACTED BUSINESS DATA:\n{extracted_json[:2000]}"  # Limit to 2000 chars
        except:
            extracted_section = "\n\nEXTRACTED BUSINESS DATA: (Available but could not serialize)"

    return f"""You are a healthcare EDI specialist. Convert the following parsed X12 {tx} EDI data into a clear, plain-English report suitable for a non-technical healthcare billing professional.

TRANSACTION TYPE: {tx}
SENDER: {env.sender_id}
RECEIVER: {env.receiver_id}
DATE: {env.interchange_date}
VERSION: {env.version}

KEY DATA:
{facts}{extracted_section}

VALIDATION RESULTS:
Valid: {val_result.is_valid}
Errors: {val_result.error_count}
Warnings: {val_result.warning_count}

{issues_text}

Write a structured report with these sections:
1. OVERVIEW — What this EDI file is and its purpose (2-3 sentences)
2. KEY PARTIES — Who is sending, receiving, billing, paying
3. FINANCIAL SUMMARY — Amounts, dates, claim counts (use bullet points)
4. VALIDATION STATUS — Plain-language explanation of any errors or warnings and exactly how to fix them
5. ACTION ITEMS — What the recipient should do next (numbered list)

Use plain English. Avoid raw EDI codes where possible. When you must use codes, explain them in parentheses.
Be concise but complete. Format numbers as currency where appropriate."""


def build_qa_prompt(question: str, edi_result: Any, val_result: Any, extracted_data: Any = None) -> str:
    """
    Build a prompt for answering follow-up questions about the EDI file.
    
    Args:
        question: User's question
        edi_result: Parsed EDI result (ParsedEDI object)
        val_result: Validation result (ValidationResult object)
        extracted_data: Optional extracted business data
        
    Returns:
        Formatted prompt string for LLM
    """
    import json
    
    tx = edi_result.envelope.transaction_type
    context = extract_key_facts_from_loops(tx, edi_result.loops)
    issues_brief = "; ".join(f"{err.code}: {err.message}" for err in val_result.errors[:8])
    
    # Add extracted data if provided
    extracted_section = ""
    if extracted_data:
        try:
            extracted_json = json.dumps(extracted_data, indent=2, default=str)
            extracted_section = f"\n\nEXTRACTED DATA:\n{extracted_json[:1500]}"  # Limit to 1500 chars
        except:
            extracted_section = "\n\nEXTRACTED DATA: (Available)"

    return f"""You are a healthcare EDI expert. Answer the user's question about their {tx} EDI file.

FILE CONTEXT:
{context}{extracted_section}

VALIDATION: {'Valid' if val_result.is_valid else f'{val_result.error_count} errors'}
ISSUES: {issues_brief if issues_brief else "None"}

USER QUESTION: {question}

Answer concisely in plain English. Be specific and actionable."""


def extract_key_facts_from_loops(tx: str, loops: list) -> str:
    """
    Extract key facts from parsed EDI loops based on transaction type.
    
    Args:
        tx: Transaction type (837p, 837i, 835, 834)
        loops: List of Loop objects from ParsedEDI
        
    Returns:
        Formatted string with key facts
    """
    lines = []
    
    try:
        if tx in ('837p', '837i'):
            # Extract claim information
            claim_count = 0
            total_charge = 0.0
            
            for loop in loops:
                if loop.loop_id == '2300':  # Claim loop
                    claim_count += 1
                    clm = loop.find_segment('CLM')
                    if clm:
                        try:
                            charge = float(clm.get_value(2))
                            total_charge += charge
                        except:
                            pass
            
            lines.append(f"• Total Claims: {claim_count}")
            if total_charge > 0:
                lines.append(f"• Total Billed Amount: ${total_charge:,.2f}")
        
        elif tx == '835':
            # Extract payment information
            for loop in loops:
                bpr = loop.find_segment('BPR')
                if bpr:
                    try:
                        amount = float(bpr.get_value(2))
                        lines.append(f"• Total Payment: ${amount:,.2f}")
                        lines.append(f"• Payment Date: {bpr.get_value(16)}")
                    except:
                        pass
                    break
        
        elif tx == '834':
            # Extract enrollment information
            member_count = 0
            for loop in loops:
                if loop.loop_id == '2000':  # Member loop
                    member_count += 1
            
            lines.append(f"• Total Members: {member_count}")
    
    except Exception as e:
        lines.append(f"• Error extracting facts: {str(e)}")
    
    return "\n".join(lines) if lines else "No structured data extracted."


def extract_key_facts(tx: str, parsed: dict) -> str:
    """
    DEPRECATED: Use extract_key_facts_from_loops instead.
    
    Extract key facts from parsed EDI data based on transaction type.
    
    Args:
        tx: Transaction type (837P, 837I, 835, 834)
        parsed: Parsed EDI data dictionary
        
    Returns:
        Formatted string with key facts
    """
    lines = []

    if tx.startswith("837"):
        # 837 Professional/Institutional Claims
        bh = parsed.get("transaction_purpose", {})
        if bh:
            lines.append(f"• Transaction Purpose: {bh.get('purpose', '')} — {bh.get('transaction_type', '')}")
            lines.append(f"• Submission Date: {bh.get('date', '')}")
        
        sub = parsed.get("submitter", {})
        if sub:
            lines.append(f"• Submitter: {sub.get('name', '')} (ID: {sub.get('id', '')})")
        
        bp = parsed.get("billing_provider", {})
        if bp:
            lines.append(f"• Billing Provider: {bp.get('name', '')} (NPI: {bp.get('id', '')})")
        
        claims = parsed.get("claims", [])
        lines.append(f"• Total Claims: {len(claims)}")
        
        # Calculate total billed
        total = sum(
            float(c.get("total_charge", "$0").replace("$", "").replace(",", ""))
            for c in claims
        )
        lines.append(f"• Total Billed Amount: ${total:,.2f}")
        
        # Show first 3 claims
        for i, claim in enumerate(claims[:3], 1):
            lines.append(f"\nCLAIM #{i}: {claim.get('claim_id', '')}")
            lines.append(f"  Charge: {claim.get('total_charge', '')}")
            diags = claim.get("diagnosis_codes", [])
            if diags:
                lines.append(f"  Diagnoses: {', '.join(d['code'] for d in diags[:3])}")

    elif tx == "835":
        # 835 Remittance Advice
        fi = parsed.get("financial_info", {})
        if fi:
            lines.append(f"• Total Payment: {fi.get('total_payment_amount', '')}")
            lines.append(f"• Payment Method: {fi.get('payment_method', '')}")
            lines.append(f"• Payment Date: {fi.get('check_eft_date', '')}")
        
        payer = parsed.get("payer", {})
        payee = parsed.get("payee", {})
        if payer:
            lines.append(f"• Payer: {payer.get('name', '')}")
        if payee:
            lines.append(f"• Payee/Provider: {payee.get('name', '')}")
        
        claims = parsed.get("claim_payments", [])
        lines.append(f"• Claims in Remittance: {len(claims)}")

    elif tx == "834":
        # 834 Benefit Enrollment
        lines.append(f"• Transaction Purpose: {parsed.get('transaction_purpose', '')}")
        lines.append(f"• Effective Date: {parsed.get('effective_date', '')}")
        
        sponsor = parsed.get("sponsor", {})
        payer = parsed.get("payer", {})
        if sponsor:
            lines.append(f"• Plan Sponsor: {sponsor.get('name', '')}")
        if payer:
            lines.append(f"• Insurance Carrier: {payer.get('name', '')}")
        
        members = parsed.get("members", [])
        lines.append(f"• Total Members: {len(members)}")

    return "\n".join(lines) if lines else "No structured data extracted."
