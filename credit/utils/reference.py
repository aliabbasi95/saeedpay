# credit/utils/reference.py

import random
import string


def generate_credit_reference():
    """Generate unique reference code for credit limits"""
    return f"CR{random.randint(100000, 999999)}"


def generate_statement_reference():
    """Generate unique reference code for statements"""
    return f"ST{random.randint(100000, 999999)}"


def generate_decision_reference():
    """Generate unique reference code for credit decisions"""
    return f"CD{random.randint(100000, 999999)}"
