"""
Builtin validation handlers registry.
"""

from typing import Callable
from validedi.handlers.npi import luhn_check
from validedi.handlers.cross_segment import (
    charge_total_consistency,
    charge_total_consistency_i,
    date_range_check,
    dob_vs_claim_date,
    coverage_date_consistency,
)
from validedi.handlers.duplicate_check import duplicate_member_check
from validedi.handlers.diagnosis_codes import validate_diagnosis_code
from validedi.handlers.remittance import (
    bpr_clp_total_match,
    duplicate_bht_check,
    cas_balance_check,
    missing_svc_check,
    plb_orphan_check,
)
from validedi.handlers.claim_checks import (
    clm_frequency_code_check,
    all_zero_charges_check,
    admission_type_check,
    drg_code_check,
    luhn_check_rendering,
    diagnosis_decimal_check,
)

# Registry mapping handler names to callables
BUILTIN_HANDLERS: dict[str, Callable] = {
    'luhn_check': luhn_check,
    'luhn_check_rendering': luhn_check_rendering,
    'charge_total_consistency': charge_total_consistency,
    'charge_total_consistency_i': charge_total_consistency_i,
    'date_range_check': date_range_check,
    'coverage_date_consistency': coverage_date_consistency,
    'dob_vs_claim_date': dob_vs_claim_date,
    'duplicate_member_check': duplicate_member_check,
    'validate_diagnosis_code': validate_diagnosis_code,
    'bpr_clp_total_match': bpr_clp_total_match,
    'duplicate_bht_check': duplicate_bht_check,
    'cas_balance_check': cas_balance_check,
    'missing_svc_check': missing_svc_check,
    'plb_orphan_check': plb_orphan_check,
    'clm_frequency_code_check': clm_frequency_code_check,
    'all_zero_charges_check': all_zero_charges_check,
    'admission_type_check': admission_type_check,
    'drg_code_check': drg_code_check,
    'diagnosis_decimal_check': diagnosis_decimal_check,
}

__all__ = ['BUILTIN_HANDLERS']
