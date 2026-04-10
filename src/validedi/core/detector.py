"""
Transaction Type Detector

Responsibilities:
- Auto-detect transaction type from ST01 segment (837, 835, 834)
- Detect subtype from ST03 or GS08 (837P vs 837I)
- Return transaction type enum: TransactionType.P837P, P837I, P835, P834
- Handle unknown/unsupported transaction types gracefully

Input: Parsed envelope or ST segment
Output: TransactionType enum
"""
