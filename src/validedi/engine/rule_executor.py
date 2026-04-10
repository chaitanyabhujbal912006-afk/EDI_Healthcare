"""
Rule executor — evaluates all YAML-defined rules and builtin handlers
against a parsed EDI transaction.
"""

import re
from datetime import datetime
from typing import Any

from validedi.engine.models import Loop, Segment, ParsedEDI, ValidationError
from validedi.engine.config_loader import TransactionConfig, RuleConfig
from validedi.handlers import BUILTIN_HANDLERS


class RuleExecutor:
    """Executes all validation rules against a parsed EDI document."""

    def __init__(self, config: TransactionConfig):
        self.config = config

    # ──────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────────

    def execute_all(self, loops: list[Loop], parsed: ParsedEDI) -> list[ValidationError]:
        """Run every rule in the config against the parsed document."""
        errors: list[ValidationError] = []
        txn_type = parsed.envelope.transaction_type  # e.g. '837p', '835', '834'

        for rule in self.config.rules.values():
            # Skip rules that don't apply to this transaction type
            if rule.transaction_types and txn_type not in rule.transaction_types:
                continue
            try:
                errors.extend(self._execute_rule(rule, loops, parsed))
            except Exception as exc:  # never let a single rule crash the whole run
                errors.append(ValidationError(
                    code=rule.id,
                    severity='warning',
                    segment='UNKNOWN',
                    element=None,
                    loop=None,
                    position=0,
                    message=f'Rule {rule.id} raised an unexpected error: {exc}',
                ))

        return errors

    # ──────────────────────────────────────────────────────────────────────────
    # Rule dispatch
    # ──────────────────────────────────────────────────────────────────────────

    def _execute_rule(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        dispatch = {
            'required_segment':    self._rule_required_segment,
            'required_element':    self._rule_required_element,
            'required_entity':     self._rule_required_entity,
            'code_set':            self._rule_code_set,
            'composite_code_set':  self._rule_composite_code_set,
            'regex':               self._rule_regex,
            'numeric_validation':  self._rule_numeric_validation,
            'numeric_range':       self._rule_numeric_range,
            'date_format':         self._rule_date_format,
            'control_number_match':self._rule_control_number_match,
            'segment_count':       self._rule_segment_count,
            'paired_segments':     self._rule_paired_segments,
            'sequential_numbering':self._rule_sequential_numbering,
            'minimum_count':       self._rule_minimum_count,
            'conditional_required':self._rule_conditional_required,
            'expression':          self._rule_expression,
            'builtin':             self._rule_builtin,
            'isa_fixed_width':     self._rule_isa_fixed_width,
            'delimiter_collision': self._rule_delimiter_collision,
            'duplicate_gs':        self._rule_duplicate_gs,
            'wrong_st_code':       self._rule_wrong_st_code,
        }
        handler = dispatch.get(rule.type)
        if handler is None:
            return []
        return handler(rule, loops, parsed)

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _all_segments(self, loops: list[Loop]) -> list[Segment]:
        """Flatten all segments from all loops recursively."""
        segs: list[Segment] = []
        for loop in loops:
            segs.extend(loop.segments)
            segs.extend(self._all_segments(loop.children))
        return segs

    def _find_segments(self, seg_id: str, loops: list[Loop]) -> list[Segment]:
        return [s for s in self._all_segments(loops) if s.segment_id == seg_id]

    def _find_segments_in_loop(
        self, seg_id: str, loop_id: str, loops: list[Loop]
    ) -> list[Segment]:
        """Find segments only within loops matching loop_id."""
        result: list[Segment] = []
        for loop in loops:
            if loop.loop_id == loop_id:
                result.extend(s for s in loop.segments if s.segment_id == seg_id)
            result.extend(self._find_segments_in_loop(seg_id, loop_id, loop.children))
        return result

    def _loops_with_id(self, loop_id: str, loops: list[Loop]) -> list[Loop]:
        result: list[Loop] = []
        for loop in loops:
            if loop.loop_id == loop_id:
                result.append(loop)
            result.extend(self._loops_with_id(loop_id, loop.children))
        return result

    def _fmt(self, rule: RuleConfig, **kwargs: Any) -> str:
        try:
            return rule.message.format(**kwargs)
        except (KeyError, IndexError):
            return rule.message

    # ──────────────────────────────────────────────────────────────────────────
    # Rule implementations
    # ──────────────────────────────────────────────────────────────────────────

    def _rule_required_segment(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        # Envelope segments (ISA, IEA, GS, GE, ST, SE) are handled by the parser
        # and stored in envelope metadata — don't flag them as missing from loops
        envelope_segments = {'ISA', 'IEA', 'GS', 'GE', 'ST', 'SE'}
        if rule.target in envelope_segments:
            return self._check_envelope_segment(rule, parsed)

        segs = self._find_segments(rule.target, loops)
        if not segs:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment=rule.target, element=None, loop=rule.loop,
                position=0, message=self._fmt(rule),
            )]
        return []

    def _check_envelope_segment(
        self, rule: RuleConfig, parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check envelope segment presence via parsed envelope metadata."""
        env = parsed.envelope
        # If we have valid envelope metadata, the segment exists
        # Only flag if the metadata fields are empty/missing
        checks = {
            'ISA': bool(env.isa_control_number),
            'IEA': bool(env.isa_control_number),  # IEA presence implied by successful parse
            'GS':  bool(env.gs_control_number),
            'GE':  bool(env.gs_control_number),
            'ST':  bool(env.st_control_number),
            'SE':  bool(env.st_control_number),
        }
        present = checks.get(rule.target, True)
        if not present:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment=rule.target, element=None, loop=rule.loop,
                position=0, message=self._fmt(rule),
            )]
        return []

    def _rule_required_element(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check that a specific element (e.g. CLM01) is not blank."""
        errors: list[ValidationError] = []
        seg_id = rule.target[:3] if rule.target else ''
        try:
            elem_idx = int(rule.target[3:]) if len(rule.target) > 3 else 1
        except ValueError:
            elem_idx = 1

        segs = self._find_segments(seg_id, loops)
        for seg in segs:
            val = seg.get_value(elem_idx).strip()
            if not val:
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment=seg_id, element=rule.target, loop=rule.loop,
                    position=seg.position, message=self._fmt(rule, value=val),
                ))
        return errors

    def _rule_required_entity(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check that an NM1/N1 with a specific entity qualifier exists."""
        seg_id = rule.target  # e.g. 'NM1' or 'N1'
        entity_code = rule.entity_code

        if rule.loop:
            segs = self._find_segments_in_loop(seg_id, rule.loop, loops)
        else:
            segs = self._find_segments(seg_id, loops)

        for seg in segs:
            if seg.get_value(1) == entity_code:
                return []

        return [ValidationError(
            code=rule.id, severity=rule.severity,
            segment=seg_id, element=f'{seg_id}01', loop=rule.loop,
            position=0, message=self._fmt(rule),
        )]

    def _rule_code_set(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        seg_id = rule.target[:3] if rule.target else ''
        try:
            elem_idx = int(rule.target[3:]) if len(rule.target) > 3 else 1
        except ValueError:
            elem_idx = 1

        # Resolve allowed values
        allowed: set[str] = set()
        if rule.allowed_values:
            allowed = set(rule.allowed_values)
        elif rule.code_set_id and rule.code_set_id in self.config.code_sets:
            allowed = self.config.code_sets[rule.code_set_id]

        if not allowed:
            return []

        # ISA15 is an envelope element — check raw ISA
        if rule.target == 'ISA15':
            return self._check_isa_element(rule, parsed, 15, allowed)

        segs = self._find_segments(seg_id, loops)
        for seg in segs:
            val = seg.get_value(elem_idx).strip()
            if val and val not in allowed:
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment=seg_id, element=rule.target, loop=rule.loop,
                    position=seg.position, message=self._fmt(rule, value=val),
                ))
        return errors

    def _check_isa_element(
        self, rule: RuleConfig, parsed: ParsedEDI, elem_idx: int, allowed: set[str]
    ) -> list[ValidationError]:
        """Extract an ISA element from raw EDI and validate it."""
        raw = parsed.raw
        isa_start = raw.find('ISA')
        if isa_start == -1:
            return []
        isa_segment = raw[isa_start:isa_start + 106]
        element_sep = isa_segment[3] if len(isa_segment) > 3 else '*'
        elements = isa_segment.split(element_sep)
        if len(elements) <= elem_idx:
            return []
        val = elements[elem_idx].strip().rstrip('~').strip()
        if val and val not in allowed:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment='ISA', element=f'ISA{elem_idx:02d}', loop=None,
                position=0, message=self._fmt(rule, value=val),
            )]
        return []

    def _rule_composite_code_set(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        seg_id = rule.target[:3] if rule.target else ''
        try:
            elem_idx = int(rule.target[3:]) if len(rule.target) > 3 else 1
        except ValueError:
            elem_idx = 1

        allowed: set[str] = set()
        if rule.allowed_values:
            allowed = set(rule.allowed_values)
        elif rule.code_set_id and rule.code_set_id in self.config.code_sets:
            allowed = self.config.code_sets[rule.code_set_id]

        if not allowed:
            return []

        component_idx = rule.component or 1
        segs = self._find_segments(seg_id, loops)
        for seg in segs:
            elem = seg.get(elem_idx)
            if elem.components:
                val = elem.components[component_idx - 1] if component_idx <= len(elem.components) else ''
            else:
                val = elem.raw
            val = val.strip()
            if val and val not in allowed:
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment=seg_id, element=rule.target, loop=rule.loop,
                    position=seg.position, message=self._fmt(rule, value=val),
                ))
        return errors

    def _rule_regex(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        if not rule.pattern:
            return []

        seg_id = rule.target[:3] if rule.target else ''
        try:
            elem_idx = int(rule.target[3:]) if len(rule.target) > 3 else 1
        except ValueError:
            elem_idx = 1

        pattern = re.compile(rule.pattern)

        # ISA12 is an envelope element — check raw ISA
        if rule.target == 'ISA12':
            raw = parsed.raw
            isa_start = raw.find('ISA')
            if isa_start == -1:
                return []
            isa_seg = raw[isa_start:isa_start + 106]
            element_sep = isa_seg[3] if len(isa_seg) > 3 else '*'
            elements = isa_seg.split(element_sep)
            if len(elements) <= 12:
                return []
            val = elements[12].strip()
            if val and not pattern.match(val):
                return [ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment='ISA', element='ISA12', loop=None,
                    position=0, message=self._fmt(rule, value=val),
                )]
            return []

        # Respect loop filter if specified
        if rule.loop:
            segs = self._find_segments_in_loop(seg_id, rule.loop, loops)
        else:
            segs = self._find_segments(seg_id, loops)

        for seg in segs:
            val = seg.get_value(elem_idx).strip()
            if val and not pattern.match(val):
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment=seg_id, element=rule.target, loop=rule.loop,
                    position=seg.position, message=self._fmt(rule, value=val),
                ))
        return errors

    def _rule_numeric_validation(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        seg_id = rule.target[:3] if rule.target else ''
        try:
            elem_idx = int(rule.target[3:]) if len(rule.target) > 3 else 1
        except ValueError:
            elem_idx = 1

        segs = self._find_segments(seg_id, loops)
        for seg in segs:
            val = seg.get_value(elem_idx).strip()
            if not val:
                continue
            try:
                float(val)
            except ValueError:
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment=seg_id, element=rule.target, loop=rule.loop,
                    position=seg.position, message=self._fmt(rule, value=val),
                ))
        return errors

    def _rule_numeric_range(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        seg_id = rule.target[:3] if rule.target else ''
        try:
            elem_idx = int(rule.target[3:]) if len(rule.target) > 3 else 1
        except ValueError:
            elem_idx = 1

        segs = self._find_segments(seg_id, loops)
        for seg in segs:
            val = seg.get_value(elem_idx).strip()
            if not val:
                continue
            try:
                num = float(val)
            except ValueError:
                continue

            violated = False
            if rule.min_value is not None and num < rule.min_value:
                violated = True
            if rule.max_value is not None and num > rule.max_value:
                violated = True

            if violated:
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment=seg_id, element=rule.target, loop=rule.loop,
                    position=seg.position, message=self._fmt(rule, value=val),
                ))
        return errors

    def _rule_date_format(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Validate DTP03 is a real CCYYMMDD date."""
        errors: list[ValidationError] = []
        segs = self._find_segments('DTP', loops)
        for seg in segs:
            qualifier = seg.get_value(2).strip()
            if rule.expected_format and qualifier != rule.expected_format:
                continue  # only validate D8 format qualifiers
            val = seg.get_value(3).strip()
            if not val:
                continue
            # Handle date ranges (CCYYMMDD-CCYYMMDD)
            date_str = val.split('-')[0] if '-' in val else val
            if not re.match(r'^\d{8}$', date_str):
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment='DTP', element='DTP03', loop=rule.loop,
                    position=seg.position, message=self._fmt(rule, value=val),
                ))
                continue
            try:
                datetime.strptime(date_str, '%Y%m%d')
            except ValueError:
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment='DTP', element='DTP03', loop=rule.loop,
                    position=seg.position, message=self._fmt(rule, value=val),
                ))
        return errors

    def _rule_control_number_match(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Compare envelope control numbers using parsed envelope metadata."""
        env = parsed.envelope

        # Map references to envelope metadata values
        env_values = {
            'ISA13': env.isa_control_number,
            'IEA02': env.isa_control_number,  # same field — mismatch means raw IEA02 differs
            'GS06':  env.gs_control_number,
            'GE02':  env.gs_control_number,
            'ST02':  env.st_control_number,
            'SE02':  env.st_control_number,
        }

        # For envelope-level checks, extract raw values from the EDI
        raw = parsed.raw
        if not raw:
            return []

        def get_raw_element(seg_id: str, elem_idx: int) -> str:
            """Extract element from raw EDI by segment ID."""
            isa_start = raw.find('ISA')
            if isa_start == -1:
                return ''
            element_sep = raw[isa_start + 3] if len(raw) > isa_start + 3 else '*'
            seg_term = raw[isa_start + 105] if len(raw) > isa_start + 105 else '~'
            segments = raw.split(seg_term)
            for seg in segments:
                seg = seg.strip()
                if seg.startswith(seg_id + element_sep):
                    parts = seg.split(element_sep)
                    if len(parts) > elem_idx:
                        return parts[elem_idx].strip()
            return ''

        src_ref = rule.source or ''
        tgt_ref = rule.target or ''

        src_seg = src_ref[:3]
        tgt_seg = tgt_ref[:3]
        try:
            src_idx = int(src_ref[3:]) if len(src_ref) > 3 else 1
            tgt_idx = int(tgt_ref[3:]) if len(tgt_ref) > 3 else 1
        except ValueError:
            src_idx, tgt_idx = 1, 1

        src_val = get_raw_element(src_seg, src_idx)
        tgt_val = get_raw_element(tgt_seg, tgt_idx)

        if not src_val or not tgt_val:
            # Fall back to loop-based search
            src_segs = self._find_segments(src_seg, loops)
            tgt_segs = self._find_segments(tgt_seg, loops)
            if not src_segs or not tgt_segs:
                return []
            src_val = src_segs[0].get_value(src_idx).strip()
            tgt_val = tgt_segs[0].get_value(tgt_idx).strip()

        if src_val and tgt_val and src_val != tgt_val:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment=tgt_seg, element=tgt_ref, loop=rule.loop,
                position=0,
                message=self._fmt(rule, source_value=src_val, target_value=tgt_val),
            )]
        return []

    def _rule_segment_count(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Validate SE01 matches actual segment count."""
        se_segs = self._find_segments('SE', loops)
        st_segs = self._find_segments('ST', loops)
        if not se_segs or not st_segs:
            return []

        reported_str = se_segs[0].get_value(1).strip()
        try:
            reported = int(reported_str)
        except ValueError:
            return []

        # Count all segments from ST through SE inclusive
        all_segs = self._all_segments(loops)
        # Find positions of ST and SE
        st_pos = st_segs[0].position
        se_pos = se_segs[0].position
        actual = sum(1 for s in all_segs if st_pos <= s.position <= se_pos)

        if reported != actual:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment='SE', element='SE01', loop=rule.loop,
                position=se_segs[0].position,
                message=self._fmt(rule, reported=reported, actual=actual),
            )]
        return []

    def _rule_paired_segments(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check that paired segments (GS/GE, ST/SE) have equal counts."""
        if not rule.segment_pair or len(rule.segment_pair) < 2:
            return []
        open_id, close_id = rule.segment_pair[0], rule.segment_pair[1]
        open_count = len(self._find_segments(open_id, loops))
        close_count = len(self._find_segments(close_id, loops))
        if open_count != close_count:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment=open_id, element=None, loop=rule.loop,
                position=0,
                message=self._fmt(rule, gs_count=open_count, ge_count=close_count,
                                  st_count=open_count, se_count=close_count),
            )]
        return []

    def _rule_sequential_numbering(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check HL01 is sequential starting at 1."""
        errors: list[ValidationError] = []
        seg_id = rule.target[:3] if rule.target else 'HL'
        try:
            elem_idx = int(rule.target[3:]) if len(rule.target) > 3 else 1
        except ValueError:
            elem_idx = 1

        segs = self._find_segments(seg_id, loops)
        for i, seg in enumerate(segs):
            val = seg.get_value(elem_idx).strip()
            expected = str(i + 1)
            if val and val != expected:
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment=seg_id, element=rule.target, loop=rule.loop,
                    position=seg.position,
                    message=self._fmt(rule, index=i + 1, value=val, expected=expected),
                ))
        return errors

    def _rule_minimum_count(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check that at least min_count segments exist."""
        segs = self._find_segments(rule.target, loops)
        count = len(segs)
        min_count = rule.min_count or 1
        if count < min_count:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment=rule.target, element=None, loop=rule.loop,
                position=0, message=self._fmt(rule, count=count),
            )]
        return []

    def _rule_conditional_required(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """If condition_segment exists, required_segment must also exist."""
        cond_segs = self._find_segments(rule.condition_segment or '', loops)
        if not cond_segs:
            return []
        req_segs = self._find_segments(rule.required_segment or '', loops)
        if not req_segs:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment=rule.required_segment or '', element=None, loop=rule.loop,
                position=0, message=self._fmt(rule),
            )]
        return []

    def _rule_expression(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Evaluate simple element comparison expressions like 'CLP04 <= CLP03'."""
        errors: list[ValidationError] = []
        if not rule.expression:
            return []

        # Parse expression: 'ELEM OP ELEM'
        expr_match = re.match(
            r'([A-Z]{2,3}\d{2})\s*(<=|>=|<|>|==|!=)\s*([A-Z]{2,3}\d{2})',
            rule.expression
        )
        if not expr_match:
            return []

        lhs_ref, op, rhs_ref = expr_match.groups()
        lhs_seg = lhs_ref[:3]
        rhs_seg = rhs_ref[:3]
        try:
            lhs_idx = int(lhs_ref[3:])
            rhs_idx = int(rhs_ref[3:])
        except ValueError:
            return []

        # Find loops to evaluate in
        target_loops = self._loops_with_id(rule.loop, loops) if rule.loop else loops

        for tloop in target_loops:
            all_segs = tloop.segments
            lhs_seg_obj = next((s for s in all_segs if s.segment_id == lhs_seg), None)
            rhs_seg_obj = next((s for s in all_segs if s.segment_id == rhs_seg), None)
            if not lhs_seg_obj or not rhs_seg_obj:
                continue
            try:
                lhs_val = float(lhs_seg_obj.get_value(lhs_idx))
                rhs_val = float(rhs_seg_obj.get_value(rhs_idx))
            except ValueError:
                continue

            ops = {'<=': lhs_val <= rhs_val, '>=': lhs_val >= rhs_val,
                   '<': lhs_val < rhs_val, '>': lhs_val > rhs_val,
                   '==': lhs_val == rhs_val, '!=': lhs_val != rhs_val}
            if not ops.get(op, True):
                errors.append(ValidationError(
                    code=rule.id, severity=rule.severity,
                    segment=lhs_seg, element=lhs_ref, loop=rule.loop,
                    position=lhs_seg_obj.position,
                    message=self._fmt(rule),
                ))
        return errors

    def _rule_builtin(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Dispatch to a registered builtin handler."""
        handler_fn = BUILTIN_HANDLERS.get(rule.handler or '')
        if not handler_fn:
            return []

        # Scope determines what we pass to the handler
        if rule.scope == 'transaction':
            return handler_fn(loops)
        elif rule.loop:
            target_loops = self._loops_with_id(rule.loop, loops)
            errors: list[ValidationError] = []
            for tloop in target_loops:
                errors.extend(handler_fn(tloop))
            return errors
        else:
            return handler_fn(loops)

    def _rule_isa_fixed_width(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check ISA segment is exactly 106 characters."""
        # Find ISA in raw content
        raw = parsed.raw
        isa_start = raw.find('ISA')
        if isa_start == -1:
            return []
        # ISA ends at the segment terminator (char at position 105 from ISA start)
        # ISA is always 106 chars including the segment terminator
        isa_segment = raw[isa_start:isa_start + 106]
        if len(isa_segment) < 106:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment='ISA', element=None, loop=None,
                position=0,
                message=self._fmt(rule, length=len(isa_segment)),
            )]
        return []

    def _rule_delimiter_collision(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check for delimiter characters appearing inside data element values."""
        errors: list[ValidationError] = []
        raw = parsed.raw
        if len(raw) < 106:
            return []

        # Extract delimiters from ISA
        isa_start = raw.find('ISA')
        if isa_start == -1:
            return []
        element_sep = raw[isa_start + 3] if len(raw) > isa_start + 3 else '*'
        comp_sep = raw[isa_start + 104] if len(raw) > isa_start + 104 else ':'
        seg_term = raw[isa_start + 105] if len(raw) > isa_start + 105 else '~'

        all_segs = self._all_segments(loops)
        for seg in all_segs:
            if seg.segment_id in ('ISA', 'IEA'):
                continue
            for i, elem in enumerate(seg.elements):
                val = elem.raw
                # Check if element_sep appears in value (excluding composite separator)
                if element_sep in val and element_sep != comp_sep:
                    errors.append(ValidationError(
                        code=rule.id, severity=rule.severity,
                        segment=seg.segment_id,
                        element=f'{seg.segment_id}{i + 1:02d}',
                        loop=None, position=seg.position,
                        message=self._fmt(
                            rule,
                            segment=seg.segment_id,
                            element=i + 1,
                            delimiter=element_sep,
                            value=val,
                        ),
                    ))
        return errors

    def _rule_duplicate_gs(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check for duplicate GS groups in a single interchange."""
        gs_segs = self._find_segments('GS', loops)
        if len(gs_segs) > 1:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment='GS', element=None, loop=None,
                position=gs_segs[1].position,
                message=self._fmt(rule, count=len(gs_segs)),
            )]
        return []

    def _rule_wrong_st_code(
        self, rule: RuleConfig, loops: list[Loop], parsed: ParsedEDI
    ) -> list[ValidationError]:
        """Check ST01 matches expected transaction type."""
        st_segs = self._find_segments('ST', loops)
        if not st_segs:
            return []
        st01 = st_segs[0].get_value(1).strip()
        expected = rule.target or ''
        if expected and st01 != expected:
            return [ValidationError(
                code=rule.id, severity=rule.severity,
                segment='ST', element='ST01', loop=None,
                position=st_segs[0].position,
                message=self._fmt(rule, value=st01, expected=expected),
            )]
        return []
