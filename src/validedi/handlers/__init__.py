"""
Builtin validation handlers registry.
"""

from collections.abc import Callable

from validedi.handlers.claim_checks import (
    admission_type_check,
    all_zero_charges_check,
    amount_format_check,
    clm_frequency_code_check,
    diagnosis_decimal_check,
    drg_code_check,
    dtp_date_format_check,
    luhn_check_rendering,
    qualifiers_check,
)
from validedi.handlers.cross_segment import (
    charge_total_consistency,
    charge_total_consistency_i,
    coverage_date_consistency,
    date_range_check,
    dob_vs_claim_date,
    validate_hl_hierarchy,
)
from validedi.handlers.diagnosis_codes import validate_diagnosis_code
from validedi.handlers.duplicate_check import duplicate_member_check
from validedi.handlers.npi import luhn_check, validate_billing_npi, validate_npi_segments
from validedi.handlers.remittance import (
    bpr_clp_total_match,
    cas_balance_check,
    duplicate_bht_check,
    missing_svc_check,
    plb_orphan_check,
)

# Registry mapping handler names to callables
BUILTIN_HANDLERS: dict[str, Callable] = {
    'luhn_check': luhn_check,
    'validate_npi_segments': validate_npi_segments,
    'validate_billing_npi': validate_billing_npi,
    'luhn_check_rendering': luhn_check_rendering,
    'charge_total_consistency': charge_total_consistency,
    'charge_total_consistency_i': charge_total_consistency_i,
    'date_range_check': date_range_check,
    'coverage_date_consistency': coverage_date_consistency,
    'validate_hl_hierarchy': validate_hl_hierarchy,
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
    'dtp_date_format_check': dtp_date_format_check,
    'amount_format_check': amount_format_check,
    'qualifiers_check': qualifiers_check,
}

__all__ = ['BUILTIN_HANDLERS']

