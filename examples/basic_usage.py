"""
Basic usage examples for ValidEDI library.
"""

from validedi import parse, validate

# Example 835 (Remittance Advice)
edi_835 = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*:*00501*000000001*0*P*:~
GS*HP*SENDER*RECEIVER*20230101*1200*1*X*005010X221A1~
ST*835*0001~
BPR*I*100.00*C*ACH*CCP*01*999999999*DA*123456*1234567890**01*999888777*DA*98765*20230101~
N1*PR*INSURANCE COMPANY~
N1*PE*PROVIDER NAME~
LX*1~
CLP*PATIENT123*1*200.00*100.00*0.00*12*1234567890*11*1~
SVC*HC:99213*200.00*100.00**1~
SE*9*0001~
GE*1*1~
IEA*1*000000001~"""

# Example 837P (Professional Claim)
edi_837p = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*:*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20230101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*123*20230101*1200*CH~
HL*1**20*1~
NM1*85*2*PROVIDER CLINIC*****XX*1234567893~
N3*123 MAIN ST~
N4*ANYTOWN*CA*12345~
HL*2*1*22*0~
NM1*IL*1*DOE*JOHN****MI*123456789~
DMG*D8*19800101*M~
CLM*CLAIM123*100.00***11:B:1*Y*A*Y*Y~
DTP*431*D8*20230101~
HI*ABK:Z0000~
LX*1~
SV1*HC:99213*100.00*UN*1***1~
SE*15*0001~
GE*1*1~
IEA*1*000000001~"""


def example_parse_from_string():
    """Example: Parse from string."""
    print("=== Parse from String ===")
    
    result = parse(edi_835)
    
    print(f"Transaction Type: {result.envelope.transaction_type}")
    print(f"Sender: {result.envelope.sender_id}")
    print(f"Receiver: {result.envelope.receiver_id}")
    print(f"Control Number: {result.envelope.isa_control_number}")
    print(f"Number of loops: {len(result.loops)}")
    print()


def example_parse_from_file():
    """Example: Parse from file."""
    print("=== Parse from File ===")
    
    # Save example to file
    with open('test_835.edi', 'w') as f:
        f.write(edi_835)
    
    # Parse from file path
    result = parse('test_835.edi')
    
    print(f"Transaction Type: {result.envelope.transaction_type}")
    print(f"Sender: {result.envelope.sender_id}")
    print(f"Number of loops: {len(result.loops)}")
    
    # Clean up
    import os
    os.remove('test_835.edi')
    print()


def example_validate_from_file():
    """Example: Validate from file."""
    print("=== Validate from File ===")
    
    # Save example to file
    with open('test_837p.edi', 'w') as f:
        f.write(edi_837p)
    
    # Validate from file path
    result = validate('test_837p.edi')
    
    print(f"Transaction Type: {result.parsed.envelope.transaction_type}")
    print(f"Valid: {result.is_valid}")
    print(f"Errors: {result.error_count}")
    print(f"Warnings: {result.warning_count}")
    
    if result.errors:
        print("\nValidation Issues:")
        for error in result.errors[:5]:  # Show first 5
            print(f"  [{error.severity.upper()}] {error.code}: {error.message}")
            print(f"    Location: {error.segment} at position {error.position}")
    
    # Clean up
    import os
    os.remove('test_837p.edi')
    print()


def example_loop_navigation():
    """Example: Navigate loop structure."""
    print("=== Loop Navigation ===")
    
    result = parse(edi_837p)
    
    for loop in result.loops:
        print(f"Loop: {loop.loop_id}")
        print(f"  Segments: {len(loop.segments)}")
        print(f"  Children: {len(loop.children)}")
        
        # Find specific segments
        nm1 = loop.find_segment('NM1')
        if nm1:
            print(f"  Found NM1: {nm1.get_value(3)} {nm1.get_value(4)}")
        
        # Recursively show children
        for child in loop.children:
            print(f"  Child Loop: {child.loop_id} ({len(child.segments)} segments)")
    print()


def example_error_handling():
    """Example: Error handling."""
    print("=== Error Handling ===")
    
    from validedi.utils.exceptions import EDIParseError, UnsupportedTransactionError
    
    # Invalid EDI
    invalid_edi = "ISA*00*"
    
    try:
        parse(invalid_edi)
    except EDIParseError as e:
        print(f"Parse Error: {e}")
        print(f"Preview: {e.raw_preview}")
    
    # File not found
    try:
        parse('nonexistent.edi')
    except FileNotFoundError as e:
        print(f"File Error: {e}")
    
    # Unsupported transaction
    unsupported = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*:*00501*000000001*0*P*:~
GS*XX*SENDER*RECEIVER*20230101*1200*1*X*005010~
ST*999*0001~"""
    
    try:
        parse(unsupported)
    except UnsupportedTransactionError as e:
        print(f"Unsupported: {e}")
        print(f"Detected: {e.transaction_type_detected}")
    print()


if __name__ == '__main__':
    example_parse_from_string()
    example_parse_from_file()
    example_validate_from_file()
    example_loop_navigation()
    example_error_handling()
