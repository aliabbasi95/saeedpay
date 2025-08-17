#!/usr/bin/env python
"""
Test script to verify the new Statement workflow
"""

import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saeedpay.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from persiantools.jdatetime import JalaliDate
from credit.models import Statement, StatementLine
from wallets.models import Transaction, Wallet
from credit.models.credit_limit import CreditLimit

User = get_user_model()


def create_test_user():
    """Create a test user with credit limit"""
    user, created = User.objects.get_or_create(
        username='test_user',
        defaults={'email': 'test@example.com'}
    )
    
    # Create credit limit
    credit_limit, _ = CreditLimit.objects.get_or_create(
        user=user,
        approved_limit=10000000,  # 10 million Rials
        defaults={'status': 'active'}
    )
    
    return user


def create_test_wallets(user):
    """Create test wallets for user"""
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        defaults={'balance': 0}
    )
    return wallet


def test_statement_workflow():
    """Test the complete statement workflow"""
    print("Testing Statement Workflow...")
    
    # Create test user
    user = create_test_user()
    wallet = create_test_wallets(user)
    
    # Step 1: Create initial statement
    statement = Statement.objects.get_current_statement(user)
    if not statement:
        prev_stmt = Statement.objects.filter(user=user).exclude(status="current").order_by("-year", "-month").first()
        starting_balance = prev_stmt.closing_balance if prev_stmt else 0
        statement, created = Statement.objects.get_or_create_current_statement(user, starting_balance=starting_balance)
    print(f"Initial statement: {statement.reference_code}, balance: {statement.closing_balance}")
    
    # Step 2: Add some transactions (purchases)
    for i in range(3):
        # Create a mock transaction
        transaction = Transaction.objects.create(
            from_wallet=wallet,
            to_wallet=wallet,  # Simplified for testing
            amount=500000,  # 500k Rials
            status='SUCCESS'
        )
        
        # Add to statement
        statement.add_transaction(transaction)
        print(f"Added transaction {i+1}, new balance: {statement.closing_balance}")
    
    # Step 3: Simulate month-end
    print("\nSimulating month-end processing...")
    Statement.objects.close_monthly_statements()
    
    # Check if old statement is now pending
    old_statement = Statement.objects.filter(
        user=user, 
        year=statement.year, 
        month=statement.month
    ).first()
    
    print(f"Old statement status: {old_statement.status}")
    print(f"Old statement closing balance: {old_statement.closing_balance}")
    
    # Step 4: Check new current statement
    new_statement = Statement.objects.get_current_statement(user)
    print(f"New statement: {new_statement.reference_code}")
    print(f"New statement opening balance: {new_statement.opening_balance}")
    print(f"New statement current balance: {new_statement.closing_balance}")
    
    # Step 5: Check interest line was added
    interest_line = new_statement.lines.filter(type='interest').first()
    if interest_line:
        print(f"Interest line added: {interest_line.amount}")
    else:
        print("No interest line found")
    
    # Step 6: Test minimum payment calculation
    min_payment = old_statement.calculate_minimum_payment_amount()
    print(f"Minimum payment required: {min_payment}")
    
    # Step 7: Test payment processing
    print("\nTesting payment processing...")
    payment_transaction = Transaction.objects.create(
        from_wallet=wallet,
        to_wallet=wallet,
        amount=200000,  # Partial payment
        status='SUCCESS'
    )
    
    # Add payment to old statement (simulating payment during grace period)
    old_statement.apply_payment(200000, payment_transaction)
    
    # Process payment outcome
    outcome = old_statement.process_payment_during_grace_period(200000)
    print(f"Payment outcome: {outcome}")
    
    print("\nTest completed successfully!")


if __name__ == '__main__':
    test_statement_workflow()
