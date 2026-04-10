"""
Loop Builder - Hierarchical loop tree constructor

Responsibilities:
- Transform flat segment list into hierarchical loop structure per HIPAA IG
- Identify loop boundaries based on segment triggers (e.g., NM1 starts Loop 2010)
- Build parent-child relationships between loops
- Support nested loops (e.g., Loop 2000 contains Loop 2010, 2300, 2400)
- Return tree structure for UI rendering and validation

This is the most complex component - drives the collapsible tree UI.

Input: List of segments + transaction type
Output: Root Loop object with nested children
"""
