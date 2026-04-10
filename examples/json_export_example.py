"""
Example: JSON Export and Data Extraction

This example demonstrates the new v0.3.0 features:
- Structured data extraction (claims, payments, enrollments)
- JSON export with validation results
"""

from validedi import parse, validate, export_json
from validedi.extractors import extract_claims, extract_payments, extract_enrollments
import json


def example_837p_extraction():
    """Extract structured claim data from 837P file."""
    print("=" * 70)
    print("837P Claim Extraction Example")
    print("=" * 70)
    
    # Parse the file
    parsed = parse('../sample_837p.edi')
    
    # Extract structured claim data
    claims = extract_claims(parsed)
    
    print(f"\nFound {len(claims)} claims\n")
    
    for i, claim in enumerate(claims, 1):
        print(f"Claim #{i}:")
        print(f"  ID: {claim['claim_id']}")
        print(f"  Total Charge: ${claim['total_charge']:.2f}")
        print(f"  Patient: {claim['patient'].get('first_name')} {claim['patient'].get('last_name')}")
        print(f"  Diagnoses: {len(claim['diagnoses'])} codes")
        
        for dx in claim['diagnoses']:
            print(f"    - {dx['type']}: {dx['code']}")
        
        print(f"  Service Lines: {len(claim['service_lines'])}")
        for j, line in enumerate(claim['service_lines'], 1):
            print(f"    Line {j}: {line['procedure_code']} - ${line['charge']:.2f}")
        
        print()


def example_835_extraction():
    """Extract payment data from 835 file."""
    print("=" * 70)
    print("835 Payment Extraction Example")
    print("=" * 70)
    
    # Parse the file
    parsed = parse('../sample_835.edi')
    
    # Extract payment data
    payment_data = extract_payments(parsed)
    
    print(f"\nPayment Summary:")
    print(f"  Total Amount: ${payment_data['payment_summary']['total_amount']:.2f}")
    print(f"  Payment Date: {payment_data['payment_summary']['payment_date']}")
    print(f"  Payment Method: {payment_data['payment_summary']['payment_method']}")
    
    print(f"\nPayer: {payment_data['payer'].get('name')}")
    print(f"Payee: {payment_data['payee'].get('name')}")
    
    print(f"\nClaims Paid: {len(payment_data['claims'])}")
    
    for claim in payment_data['claims']:
        print(f"\n  Claim: {claim['claim_number']}")
        print(f"    Patient: {claim['patient_name']}")
        print(f"    Charged: ${claim['total_charged']:.2f}")
        print(f"    Paid: ${claim['total_paid']:.2f}")
        print(f"    Patient Resp: ${claim['patient_responsibility']:.2f}")
        
        for service in claim['services']:
            print(f"      Service: {service['procedure_code']}")
            print(f"        Charged: ${service['charged']:.2f}, Paid: ${service['paid']:.2f}")
            
            for adj in service['adjustments']:
                print(f"        Adjustment: {adj['group']} - {adj['reason_code']} (${adj['amount']:.2f})")


def example_834_extraction():
    """Extract enrollment data from 834 file."""
    print("=" * 70)
    print("834 Enrollment Extraction Example")
    print("=" * 70)
    
    # Parse the file
    parsed = parse('../sample_834.edi')
    
    # Extract enrollment data
    enrollment_data = extract_enrollments(parsed)
    
    print(f"\nSponsor: {enrollment_data['sponsor'].get('name')}")
    print(f"Insurer: {enrollment_data['insurer'].get('name')}")
    
    print(f"\nMembers Enrolled: {len(enrollment_data['members'])}")
    
    for member in enrollment_data['members']:
        print(f"\n  Member: {member['demographics'].get('first_name')} {member['demographics'].get('last_name')}")
        print(f"    Relationship: {member['relationship']}")
        print(f"    Subscriber: {'Yes' if member['is_subscriber'] else 'No'}")
        print(f"    DOB: {member['demographics'].get('dob')}")
        print(f"    Gender: {member['demographics'].get('gender')}")
        
        if member.get('coverage'):
            print(f"    Coverage Begin: {member['coverage'].get('benefit_begin')}")
            print(f"    Coverage End: {member['coverage'].get('benefit_end', 'Ongoing')}")


def example_json_export():
    """Export parsed EDI to JSON format."""
    print("=" * 70)
    print("JSON Export Example")
    print("=" * 70)
    
    # Parse and validate
    parsed = parse('../sample_837p.edi')
    validated = validate(parsed)
    
    # Export to JSON (returns dict)
    data = export_json(parsed, validated)
    
    print(f"\nTransaction Type: {data['transaction_type']}")
    print(f"Sender: {data['envelope']['sender_id']}")
    print(f"Receiver: {data['envelope']['receiver_id']}")
    
    if 'validation' in data:
        print(f"\nValidation:")
        print(f"  Valid: {data['validation']['is_valid']}")
        print(f"  Errors: {data['validation']['error_count']}")
        print(f"  Warnings: {data['validation']['warning_count']}")
    
    if 'claims' in data:
        print(f"\nClaims: {len(data['claims'])}")
        for claim in data['claims']:
            print(f"  - {claim['claim_id']}: ${claim['total_charge']:.2f}")
    
    # Save to file (serialize to JSON string)
    with open('output.json', 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print("\n✅ JSON exported to output.json")


def example_combined_workflow():
    """Complete workflow: parse, validate, extract, export."""
    print("=" * 70)
    print("Complete Workflow Example")
    print("=" * 70)
    
    # Step 1: Parse
    print("\n1. Parsing EDI file...")
    parsed = parse('../sample_837p.edi')
    print(f"   ✓ Parsed {parsed.envelope.transaction_type} transaction")
    
    # Step 2: Validate
    print("\n2. Validating...")
    validated = validate(parsed)
    if validated.is_valid:
        print("   ✓ Validation passed")
    else:
        print(f"   ⚠ Found {validated.error_count} errors")
        for error in validated.errors[:3]:  # Show first 3
            print(f"     - {error.message}")
    
    # Step 3: Extract business data
    print("\n3. Extracting structured data...")
    claims = extract_claims(parsed)
    print(f"   ✓ Extracted {len(claims)} claims")
    
    total_billed = sum(claim['total_charge'] for claim in claims)
    print(f"   ✓ Total billed: ${total_billed:.2f}")
    
    # Step 4: Export to JSON
    print("\n4. Exporting to JSON...")
    data = export_json(parsed, validated)
    json_str = json.dumps(data, indent=2, default=str)
    print(f"   ✓ Generated {len(json_str)} bytes of JSON")
    
    print("\n✅ Workflow complete!")


if __name__ == '__main__':
    # Run examples
    try:
        example_837p_extraction()
    except Exception as e:
        print(f"837P example error: {e}")
    
    print("\n")
    
    try:
        example_835_extraction()
    except Exception as e:
        print(f"835 example error: {e}")
    
    print("\n")
    
    try:
        example_834_extraction()
    except Exception as e:
        print(f"834 example error: {e}")
    
    print("\n")
    
    try:
        example_json_export()
    except Exception as e:
        print(f"JSON export example error: {e}")
    
    print("\n")
    
    try:
        example_combined_workflow()
    except Exception as e:
        print(f"Combined workflow error: {e}")
