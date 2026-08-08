"""Basic Terraform HCL sanity checks (no terraform CLI required)."""

from __future__ import annotations

import re


def validate_terraform(hcl_code: str) -> tuple[bool, str | None]:
    """
    Run lightweight validation on generated HCL.

    Returns (passed, error_message). error_message is None when passed is True.
    """
    if not hcl_code or not hcl_code.strip():
        return False, "HCL output is empty"

    errors: list[str] = []

    if "provider" not in hcl_code and "terraform" not in hcl_code:
        errors.append("Missing terraform and/or provider block")

    if 'provider "aws"' not in hcl_code and "provider aws" not in hcl_code:
        errors.append('Missing AWS provider block (expected provider "aws")')

    open_braces = hcl_code.count("{")
    close_braces = hcl_code.count("}")
    if open_braces != close_braces:
        errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")

    open_brackets = hcl_code.count("[")
    close_brackets = hcl_code.count("]")
    if open_brackets != close_brackets:
        errors.append(f"Unbalanced brackets: {open_brackets} open, {close_brackets} close")

    # Detect common LLM placeholder patterns
    if re.search(r"\.\.\.|# TODO|PLACEHOLDER|TBD", hcl_code, re.IGNORECASE):
        errors.append("HCL contains placeholder or incomplete sections")

    resource_blocks = re.findall(r"resource\s+\"[\w_-]+\"\s+\"[\w_-]+\"", hcl_code)
    if not resource_blocks:
        errors.append("No Terraform resource blocks found")

    if errors:
        return False, "; ".join(errors)

    return True, None
