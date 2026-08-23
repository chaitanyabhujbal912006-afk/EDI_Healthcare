"""
Property-Based Test: Bug Condition Exploration
All 12 unhandled rule types silently return [] on the stub executor.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12**

This test is EXPECTED TO FAIL on unfixed code.
Failure confirms the bug exists (silent skip of 12 rule types).
"""

import pytest

from validedi.engine.models import Loop, Segment, Element, ValidationError, ParsedEDI, EnvelopeMeta
from validedi.engine.config_loader import RuleConfig, TransactionConfig
from validedi.engine.rule_executor import RuleExecutor


# ── Helpers ────────────────────────────────────────────────────────────────

def make_executor(rules: list, code_sets: dict = None):
    """Build a RuleExecutor with only the given rules loaded."""
    config = TransactionConfig(
        transaction_type='test',
        loops=[],
        rules={r.id: r for r in rules},
        code_sets=code_sets or {}
    )
    return RuleExecutor(config)


def make_segment(seg_id: str, values: list, position: int = 1) -> Segment:
    elements = [Element(raw=v, components=v.split(':')) for v in values]
    return Segment(segment_id=seg_id, elements=elements, position=position)


def make_loop(loop_id: str, segments: list, children=None) -> Loop:
    return Loop(loop_id=loop_id, segments=segments, children=children or [])


def make_parsed(raw: str = 'ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*T*:~GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~ST*837*0001~SE*3*0001~GE*1*1~IEA*1*000000001~') -> ParsedEDI:
    return ParsedEDI(
        envelope=EnvelopeMeta(
            isa_control_number='000',
            gs_control_number='1',
            st_control_number='0001',
            sender_id='SENDER',
            receiver_id='RECEIVER',
            interchange_date='240101',
            interchange_time='1200',
            version='00501',
            transaction_type='837p'
        ),
        loops=[],
        raw=raw
    )


# ── Bug Condition Exploration Test ─────────────────────────────────────────

def test_bug_condition_all_12_types_return_empty():
    """
led rule types silently return [].
    This test FAILS on unfixed code (stub) — that failure CONFIRMS the bug.
r fix, this test PASSES — confirming all 12 types now emit errors.
    """

    # 1. required_segment: no CLM segment present
    rule = RuleConfig(id='837-002', type='required_segment', target='CLM', severity='warning',
                      message='No CLM segments found')
    loop = make_loop('ROOT', [make_segment('HL', ['1', '', '20', '1'])])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "required_segment: expected error for missing CLM, got []"

    # 2. required_element: CLM01 is blank
    rule = RuleConfig(id='837-003', type='required_element', target='CLM01', severity='error',
                      message='CLM01 is blank')
    loop = make_loop('ROOT', [make_segment('CLM', ['', '500', '11', '', 'B', '1'])])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "required_element: expected error for blank CLM01, got []"

    # 3. required_entity: no NM1*40 in loop 1000B
    rule = RuleConfig(id='837-001-RECEIVER', type='required_entity', target='NM1',
                      entity_code='40', loop='1000B', severity='error',
                      message='NM1*40 missing')
    loop = make_loop('1000B', [make_segment('NM1', ['41', '2', 'SUBMITTER'])])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "required_entity: expected error for missing NM1*40, got []"

    # 4. numeric_range: CLM02 = -5.00 (below .01)
    rule = RuleConfig(id='837-004', type='numeric_range', target='CLM02', severity='warning',
                      message='CLM02 is {value}', min_value=0.01)
    loop = make_loop('ROOT', [make_segment('CLM', ['CLAIM001', '-5.00', '11'])])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "numeric_range: expected error for CLM02=-5.00, got []"

    # 5. numeric_validation: CLM02 = 'ABC'
    rule = RuleConfig(id='837-005', type='numeric_validation', target='CLM02', severity='error',
                      message='CLM02 value {value} is not numeric')
    loop = make_loop('ROOT', [make_segment('CLM', ['CLAIM001', 'ABC', '11'])])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "numeric_validation: expected error for CLM02=ABC, got []"

    # 6. date_format: DTP03 = 20240231 (Feb 31 doesn't exist)
    rule = RuleConfig(id='837-006', type='date_format', target='DTP03', severity='error',
                      message='DTP date {value} is invalid', format_qualifier='DTP02',
                      expected_format='D8')
    loop = make_loop('ROOT', [make_segment('DTP', ['472', 'D8', '20240231'])])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "date_format: expected error for 20240231, got []"

    # 7. control_number_match: ISA13=000000001, IEA02=000000002
    rule = RuleConfig(id='CTL-001', type='control_number_match', source='ISA13', target='IEA02',
                      severity='error',
                      message='IEA02 {target_value} does not match ISA13 {source_value}')
    raw = 'ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*T*:~GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~ST*837*0001~SE*4*0001~GE*1*1~IEA*1*000000002~'
    executor = make_executor([rule])
    errors = executor.execute_all([], make_parsed(raw))
    assert len(errors) > 0, "control_number_match: expected error for ISA13!=IEA02, got []"

    # 8. segment_count: SE01=5 but actual=7
    rule = RuleConfig(id='CNT-001', type='segment_count', target='SE01', severity='error',
                      message='SE01 is {reported}, actual is {actual}')
    raw = 'ISA*00*     GE*1*1~IEA*1*000000001~'
    executor = make_executor([rule])
    errors = executor.execute_all([], make_parsed(raw))
    assert len(errors) > 0, "segment_count: expected error for SE01 mismatch, got []"

    # 9. paired_segments: 2 GS, 1 GE
    rule = RuleConfig(id='ENV-007', type='paired_segments', segment_pair=['GS', 'GE'],
                      severity='error',
                      message='{gs_count} GS vs {ge_count} GE')
    raw = 'ISA*00*      101*1200*^*00501*000000001*0*T*:~GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~ST*837*0001~SE*3*0001~GE*1*1~GS*HC*SENDER*RECEIVER*20240101*1201*2*X*005010X222A1~ST*837*0002~SE*3*0002~IEA*1*000000001~'
    executor = make_executor([rule])
    errors = executor.execute_all([], make_parsed(raw))
    assert len(errors) > 0, "paired_segments: expected error for 2 GS vs 1 GE, got []"

    # 10. sequential_numbering: HL01 values 1, 2, 5 (skips 3 and 4)
    rule = RuleConfig(id='837-008', type='sequential_numbering', target='HL01', severity='warning',
                      message='HL #{index} has value {value}, expected {expected}')
    hl1 = make_segment('HL', ['1', '', '20', '1'])
    hl2 = make_segment('HL', ['2', '1', '22', '1'])
    hl5 = make_segment('HL', ['5', '2', '23', '0'])
    loop = make_loop('ROOT', [hl1, hl2, hl5])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "sequential_numbering: expected error for non-sequential HL01, got []"

    # 11. minimum_count: only 1 HL segment, min_count=2
    rule = RuleConfig(id='837-007', type='minimum_count', target='HL', severity='warning',
                      message='Only {count} HL segment(s) found', min_count=2)
    loop = make_loop('ROOT', [make_segment('HL', ['1', '', '20', '1'])])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "minimum_count: expected error for 1 HL (min=2), got []"

    # 12. conditional_required: BGN present but INS absent
    rule = RuleConfig(id='COND-001', type='conditional_required', condition_segment='BGN',
                      required_segment='INS', severity='error',
                      message='INS required when BGN present')
    loop = make_loop('ROOT', [make_segment('BGN', ['00', 'REF001', '20240101'])])
    executor = make_executor([rule])
    errors = executor.execute_all([loop], make_parsed())
    assert len(errors) > 0, "conditional_required: expected error for missing INS, got []"


# ── Preservation Baseline (skeleton for Task 2) ────────────────────────────

def test_preservation_baseline():
    """
    Skeleton for Task 2: preservation tests for the 5 existing rule types.
    Will be fully implemented in Task 2.
    """
    pass
