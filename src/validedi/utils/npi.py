"""
NPI Validation Utilities

Functions:
- validate_npi_luhn(npi: str) -> bool
  Validates 10-digit NPI using Luhn algorithm (mod 10 check digit)
  
- validate_npi_nppes(npi: str) -> NPPESResult
  Calls CMS NPPES NPI Registry API to verify NPI is active
  Returns: provider name, taxonomy, status, deactivation date
  
- format_npi(npi: str) -> str
  Pads NPI to 10 digits with leading zeros

NPPES API endpoint: https://npiregistry.cms.hhs.gov/api/?version=2.1&number={npi}

Note: NPPES validation is gated behind ENABLE_NPI_VALIDATION config flag.
"""
