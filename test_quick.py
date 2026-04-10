"""
validedi 0.1.1 - Full Feature Demo & Test
Covers: parse, validate, loop navigation, segment access,
        error handling, LLM explain (rule-based), ask_followup
"""

from pathlib import Path
from validedi import (
    parse, validate,
    ParsedEDI, ValidationResult, EnvelopeMeta, Loop, Segment, Element,
    EDIParseError, EDIValidationError, UnsupportedTransactionError,
    BadConfigError, ValidEDIError,
)
from validedi.llm import explain, ask_followup, ExplainResult

PASS = "✅"
FAIL = "❌"
results = []

def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((status, label))
    print(f"  {status}  {label}" + (f"  →  {detail}" if detail else ""))

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ─────────────────────────────────────────────────────────────
# 1. PARSE FROM FILE PATH
# ─────────────────────────────────────────────────────────────
section("1. parse() — from file path (837P)")

result_837p = parse("sample_837p.edi")
check("Returns ParsedEDI instance", isinstance(result_837p, ParsedEDI))
check("raw content is non-empty string", isinstance(result_837p.raw, str) and len(result_837p.raw) > 0)
check("loops list is populated", len(result_837p.loops) > 0, f"{len(result_837p.loops)} loops")

# ─────────────────────────────────────────────────────────────
# 2. ENVELOPE METADATA
# ─────────────────────────────────────────────────────────────
section("2. EnvelopeMeta fields")

env = result_837p.envelope
check("envelope is EnvelopeMeta", isinstance(env, EnvelopeMeta))
check("transaction_type detected", env.transaction_type != "", f"'{env.transaction_type}'")
check("sender_id present", env.sender_id.strip() != "", f"'{env.sender_id.strip()}'")
check("receiver_id present", env.receiver_id.strip() != "", f"'{env.receiver_id.strip()}'")
check("isa_control_number present", env.isa_control_number != "", f"'{env.isa_control_number}'")
check("gs_control_number present", env.gs_control_number != "", f"'{env.gs_control_number}'")
check("st_control_number present", env.st_control_number != "", f"'{env.st_control_number}'")
check("interchange_date present", env.interchange_date != "", f"'{env.interchange_date}'")
check("interchange_time present", env.interchange_time != "", f"'{env.interchange_time}'")
check("version present", env.version != "", f"'{env.version}'")

# ─────────────────────────────────────────────────────────────
# 3. PARSE FROM RAW STRING
# ─────────────────────────────────────────────────────────────
section("3. parse() — from raw EDI string")

raw_edi = Path("sample_837p.edi").read_text()
result_from_str = parse(raw_edi)
check("parse from string returns ParsedEDI", isinstance(result_from_str, ParsedEDI))
check("same transaction type as file parse", result_from_str.envelope.transaction_type == result_837p.envelope.transaction_type)
check("same loop count as file parse", len(result_from_str.loops) == len(result_837p.loops))

# ─────────────────────────────────────────────────────────────
# 4. PARSE FROM Path OBJECT
# ─────────────────────────────────────────────────────────────
section("4. parse() — from pathlib.Path object")

result_path_obj = parse(Path("sample_837p.edi"))
check("parse from Path object works", isinstance(result_path_obj, ParsedEDI))
check("envelope matches", result_path_obj.envelope.isa_control_number == env.isa_control_number)

# ─────────────────────────────────────────────────────────────
# 5. LOOP STRUCTURE & NAVIGATION
# ─────────────────────────────────────────────────────────────
section("5. Loop structure & navigation")

top_loop = result_837p.loops[0]
check("Loop has loop_id", isinstance(top_loop.loop_id, str) and top_loop.loop_id != "")
check("Loop has segments list", isinstance(top_loop.segments, list))
check("Loop has children list", isinstance(top_loop.children, list))

# find_segment
nm1 = top_loop.find_segment("NM1")
check("find_segment('NM1') returns Segment or None", nm1 is None or isinstance(nm1, Segment))

# find_all
all_nm1 = top_loop.find_all("NM1")
check("find_all('NM1') returns list", isinstance(all_nm1, list))

# find_loop (recursive child search)
found_loops = top_loop.find_loop("2300")
check("find_loop('2300') returns list", isinstance(found_loops, list), f"{len(found_loops)} found")

# ─────────────────────────────────────────────────────────────
# 6. SEGMENT & ELEMENT ACCESS
# ─────────────────────────────────────────────────────────────
section("6. Segment & Element access")

# Walk all loops to find a real segment
def find_any_segment(loops, seg_id):
    for loop in loops:
        s = loop.find_segment(seg_id)
        if s:
            return s
        s = find_any_segment(loop.children, seg_id)
        if s:
            return s
    return None

clm_seg = find_any_segment(result_837p.loops, "CLM")
if clm_seg:
    check("CLM segment found", True, f"position={clm_seg.position}")
    check("Segment has segment_id", clm_seg.segment_id == "CLM")
    check("Segment has elements list", isinstance(clm_seg.elements, list))
    check("Segment.get(1) returns Element", isinstance(clm_seg.get(1), Element))
    check("Segment.get_value(1) returns str", isinstance(clm_seg.get_value(1), str), f"'{clm_seg.get_value(1)}'")
    check("Segment.get(999) returns empty Element (OOB)", clm_seg.get(999).raw == "")
    check("Segment.get_value(999) returns empty str (OOB)", clm_seg.get_value(999) == "")

    # Element composite access
    el = clm_seg.get(1)
    check("Element.raw is str", isinstance(el.raw, str))
    check("Element.components is list", isinstance(el.components, list))
    check("Element.get(999) returns '' (OOB)", el.get(999) == "")
else:
    check("CLM segment found", False, "not found — skipping element tests")

# ─────────────────────────────────────────────────────────────
# 7. VALIDATE — 837P
# ─────────────────────────────────────────────────────────────
section("7. validate() — 837P from file")

val_result = validate("sample_837p.edi")
check("Returns ValidationResult", isinstance(val_result, ValidationResult))
check("ValidationResult.parsed is ParsedEDI", isinstance(val_result.parsed, ParsedEDI))
check("errors is a list", isinstance(val_result.errors, list))
check("is_valid is bool", isinstance(val_result.is_valid, bool), f"{val_result.is_valid}")
check("error_count is int", isinstance(val_result.error_count, int), f"{val_result.error_count} errors")
check("warning_count is int", isinstance(val_result.warning_count, int), f"{val_result.warning_count} warnings")

print(f"\n  Validation summary: is_valid={val_result.is_valid}, errors={val_result.error_count}, warnings={val_result.warning_count}")
if val_result.errors:
    print("  Sample errors/warnings:")
    for e in val_result.errors[:3]:
        print(f"    [{e.severity.upper()}] {e.code} @ {e.segment}: {e.message}")

# ─────────────────────────────────────────────────────────────
# 8. VALIDATE — 835
# ─────────────────────────────────────────────────────────────
section("8. validate() — 835 (Remittance Advice)")

val_835 = validate("sample_835.edi")
check("835 parses and validates", isinstance(val_835, ValidationResult))
check("835 transaction type", val_835.parsed.envelope.transaction_type != "")
print(f"  835 transaction_type='{val_835.parsed.envelope.transaction_type}', is_valid={val_835.is_valid}")

# ─────────────────────────────────────────────────────────────
# 9. VALIDATE — from raw string
# ─────────────────────────────────────────────────────────────
section("9. validate() — from raw EDI string")

val_from_str = validate(raw_edi)
check("validate from string returns ValidationResult", isinstance(val_from_str, ValidationResult))
check("same is_valid as file validate", val_from_str.is_valid == val_result.is_valid)

# ─────────────────────────────────────────────────────────────
# 10. VALIDATION ERROR FIELDS
# ─────────────────────────────────────────────────────────────
section("10. ValidationError object fields")

all_errors = val_result.errors + val_835.errors
if all_errors:
    err = all_errors[0]
    check("error.code is str", isinstance(err.code, str), f"'{err.code}'")
    check("error.severity is error/warning/info", err.severity in ("error", "warning", "info"), f"'{err.severity}'")
    check("error.segment is str", isinstance(err.segment, str), f"'{err.segment}'")
    check("error.message is str", isinstance(err.message, str))
    check("error.position is int", isinstance(err.position, int))
    # element and loop are optional
    check("error.element is str or None", err.element is None or isinstance(err.element, str))
    check("error.loop is str or None", err.loop is None or isinstance(err.loop, str))
else:
    print("  (no errors found — skipping field checks)")

# ─────────────────────────────────────────────────────────────
# 11. LLM EXPLAIN — rule-based (no LLM)
# ─────────────────────────────────────────────────────────────
section("11. explain() — rule-based (no LLM)")

edi_result = parse("sample_837p.edi")
explain_result = explain(edi_result, val_result)
check("Returns ExplainResult", isinstance(explain_result, ExplainResult))
check("report is non-empty string", isinstance(explain_result.report, str) and len(explain_result.report) > 0)
check("source is 'rule_based'", explain_result.source == "rule_based", f"'{explain_result.source}'")
check("metadata is dict", isinstance(explain_result.metadata, dict))
check("str(ExplainResult) == report", str(explain_result) == explain_result.report)
print(f"\n  Report preview:\n  {explain_result.report[:300]}...")

# ─────────────────────────────────────────────────────────────
# 12. LLM EXPLAIN — force_rule_based=True
# ─────────────────────────────────────────────────────────────
section("12. explain() — force_rule_based=True")

explain_forced = explain(edi_result, val_result, force_rule_based=True)
check("force_rule_based returns ExplainResult", isinstance(explain_forced, ExplainResult))
check("source is 'rule_based' when forced", explain_forced.source == "rule_based")

# ─────────────────────────────────────────────────────────────
# 13. ASK FOLLOWUP — rule-based
# ─────────────────────────────────────────────────────────────
section("13. ask_followup() — rule-based (no LLM)")

answer = ask_followup("What is the transaction type?", edi_result, val_result)
check("ask_followup returns str", isinstance(answer, str), f"'{answer[:80]}'")
check("answer is non-empty", len(answer) > 0)

answer2 = ask_followup("Are there any errors?", edi_result, val_result)
check("ask_followup 'errors' question returns str", isinstance(answer2, str))
print(f"\n  Q: 'What is the transaction type?'\n  A: {answer[:120]}")
print(f"\n  Q: 'Are there any errors?'\n  A: {answer2[:120]}")

# ─────────────────────────────────────────────────────────────
# 14. ERROR HANDLING
# ─────────────────────────────────────────────────────────────
section("14. Error handling")

# EDIParseError — completely garbage input
try:
    parse("THIS IS NOT EDI AT ALL !!!")
    check("EDIParseError raised on garbage input", False)
except EDIParseError as e:
    check("EDIParseError raised on garbage input", True, str(e)[:60])
    check("EDIParseError.raw_preview is str or None", e.raw_preview is None or isinstance(e.raw_preview, str))
except Exception as e:
    check("EDIParseError raised on garbage input", False, f"got {type(e).__name__}: {e}")

# FileNotFoundError — missing file
try:
    parse("nonexistent_file_xyz.edi")
    check("FileNotFoundError raised on missing file", False)
except FileNotFoundError as e:
    check("FileNotFoundError raised on missing file", True, str(e)[:60])
except Exception as e:
    check("FileNotFoundError raised on missing file", False, f"got {type(e).__name__}: {e}")

# UnsupportedTransactionError — valid EDI envelope but unknown transaction
unsupported_edi = (
    "ISA*00*          *00*          *ZZ*SENDER123      *ZZ*RECEIVER456    "
    "*230101*1200*^*00501*000000099*0*P*:~"
    "GS*XX*SENDER123*RECEIVER456*20230101*1200*99*X*005010~"
    "ST*999*0001~SE*2*0001~GE*1*99~IEA*1*000000099~"
)
try:
    parse(unsupported_edi)
    check("UnsupportedTransactionError raised on unknown tx", False, "no exception raised")
except UnsupportedTransactionError as e:
    check("UnsupportedTransactionError raised on unknown tx", True, str(e)[:60])
    check("transaction_type_detected attr present", hasattr(e, "transaction_type_detected"))
except (EDIParseError, ValidEDIError) as e:
    check("ValidEDIError family raised on unknown tx", True, f"{type(e).__name__}: {str(e)[:60]}")
except Exception as e:
    check("UnsupportedTransactionError raised on unknown tx", False, f"got {type(e).__name__}: {e}")

# ValidEDIError is base of all custom exceptions
check("EDIParseError is subclass of ValidEDIError", issubclass(EDIParseError, ValidEDIError))
check("EDIValidationError is subclass of ValidEDIError", issubclass(EDIValidationError, ValidEDIError))
check("UnsupportedTransactionError is subclass of ValidEDIError", issubclass(UnsupportedTransactionError, ValidEDIError))
check("BadConfigError is subclass of ValidEDIError", issubclass(BadConfigError, ValidEDIError))

# ─────────────────────────────────────────────────────────────
# 15. BATCH PROCESSING PATTERN
# ─────────────────────────────────────────────────────────────
section("15. Batch processing pattern")

import glob
edi_files = glob.glob("*.edi")
batch_results = {}
for fp in edi_files:
    r = validate(fp)
    batch_results[fp] = r
    print(f"  {fp}: is_valid={r.is_valid}, errors={r.error_count}, warnings={r.warning_count}")

check("Batch processed all .edi files", len(batch_results) == len(edi_files), f"{len(batch_results)} files")

# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
section("SUMMARY")
passed = sum(1 for s, _ in results if s == PASS)
failed = sum(1 for s, _ in results if s == FAIL)
print(f"\n  {PASS} Passed: {passed}")
print(f"  {FAIL} Failed: {failed}")
print(f"  Total:  {passed + failed}")
if failed:
    print("\n  Failed checks:")
    for s, label in results:
        if s == FAIL:
            print(f"    {FAIL} {label}")
