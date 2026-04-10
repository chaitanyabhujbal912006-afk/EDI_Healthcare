"""
Loop builder - constructs hierarchical loop structure from flat segments.
"""

from validedi.engine.models import Segment, Loop
from validedi.engine.config_loader import TransactionConfig, LoopConfig


def build_loops(segments: list[Segment], config: TransactionConfig) -> list[Loop]:
    """
    Build hierarchical loop structure from flat segment list.
    
    Args:
        segments: Flat list of segments (excluding envelope segments)
        config: Transaction configuration
        
    Returns:
        List of top-level Loop objects
    """
    if not segments:
        return []
    
    # Stack to track current loop hierarchy
    stack: list[Loop] = []
    root_loops: list[Loop] = []
    
    for segment in segments:
        # Check if this segment triggers a new loop
        matching_loop = _find_matching_loop(segment, config.loops)
        
        if matching_loop:
            # Create new loop
            new_loop = Loop(
                loop_id=matching_loop.id,
                segments=[segment],
                children=[]
            )
            
            # Determine where to attach this loop
            if matching_loop.parent_id is None:
                # Top-level loop
                root_loops.append(new_loop)
                stack = [new_loop]
            else:
                # Find parent in stack
                parent_loop = _find_parent_in_stack(stack, matching_loop.parent_id)
                if parent_loop:
                    parent_loop.children.append(new_loop)
                    # Pop stack back to parent level and add new loop
                    while stack and stack[-1].loop_id != matching_loop.parent_id:
                        stack.pop()
                    stack.append(new_loop)
                else:
                    # Parent not found, treat as top-level
                    root_loops.append(new_loop)
                    stack = [new_loop]
        else:
            # Add segment to current loop
            if stack:
                stack[-1].segments.append(segment)
            else:
                # No loop context, create a default root loop
                if not root_loops:
                    root_loops.append(Loop(loop_id='ROOT', segments=[], children=[]))
                    stack = [root_loops[0]]
                root_loops[0].segments.append(segment)
    
    return root_loops


def _find_matching_loop(segment: Segment, loop_configs: list[LoopConfig]) -> LoopConfig | None:
    """Find loop configuration that matches this segment."""
    for loop_config in loop_configs:
        if segment.segment_id != loop_config.trigger_segment:
            continue
        
        # Check qualifier if specified
        if loop_config.trigger_qualifier:
            element_num = loop_config.trigger_qualifier.get('element')
            expected_value = loop_config.trigger_qualifier.get('value')
            
            if element_num and expected_value:
                actual_value = segment.get_value(element_num)
                if actual_value == expected_value:
                    return loop_config
        else:
            # No qualifier, just segment match
            return loop_config
    
    return None


def _find_parent_in_stack(stack: list[Loop], parent_id: str) -> Loop | None:
    """Find parent loop in the stack."""
    for loop in reversed(stack):
        if loop.loop_id == parent_id:
            return loop
    return None
