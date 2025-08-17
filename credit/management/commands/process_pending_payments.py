#!/usr/bin/env python
"""
Management command to process pending payments and handle grace period outcomes
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from persiantools.jdatetime import JalaliDate
from credit.models import Statement
from credit.utils.constants import MINIMUM_PAYMENT_THRESHOLD


class Command(BaseCommand):
    help = 'Process pending payments and handle grace period outcomes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Processing pending payments and grace periods...")
        
        # Get all pending payment statements
        pending_statements = Statement.objects.filter(status='pending_payment')
        
        processed_count = 0
        penalty_count = 0
        no_penalty_count = 0
        
        for statement in pending_statements:
            # Check if grace period has ended
            grace_end = statement.grace_ends_at
            if not grace_end:
                continue
                
            if timezone.now() > grace_end:
                # Grace period has ended, process outcome
                
                # Calculate total payments received during grace period
                payments = statement.lines.filter(
                    type='payment',
                    created_at__gte=statement.closed_at,
                    created_at__lte=grace_end
                )
                total_payments = sum(payment.amount for payment in payments)
                
                if not dry_run:
                    # Process payment outcome
                    outcome = statement.process_payment_during_grace_period(total_payments)
                    
                    if outcome == 'closed_no_penalty':
                        no_penalty_count += 1
                        self.stdout.write(
                            f"Statement {statement.reference_code} closed without penalty"
                        )
                        
                        # Add repayment to current statement
                        current_statement = Statement.objects.get_current_statement(statement.user)
                        if current_statement and total_payments > 0:
                            current_statement.add_line(
                                type='repayment',
                                amount=total_payments,
                                description=f"بازپرداخت بدهی دوره {statement.year}/{statement.month:02d}"
                            )
                    
                    elif outcome == 'closed_with_penalty':
                        penalty_count += 1
                        self.stdout.write(
                            f"Statement {statement.reference_code} closed with penalty"
                        )
                        
                        # Apply penalty to current statement
                        statement.apply_penalty_to_current_statement()
                else:
                    # Dry run - just report what would happen
                    min_required = statement.calculate_minimum_payment_amount()
                    debt_amount = abs(statement.closing_balance) if statement.closing_balance < 0 else 0
                    
                    if debt_amount < MINIMUM_PAYMENT_THRESHOLD:  # MINIMUM_PAYMENT_THRESHOLD
                        self.stdout.write(
                            f"DRY RUN: Statement {statement.reference_code} would close without penalty (below threshold)"
                        )
                    elif total_payments >= min_required:
                        self.stdout.write(
                            f"DRY RUN: Statement {statement.reference_code} would close without penalty (paid {total_payments} >= {min_required})"
                        )
                    else:
                        self.stdout.write(
                            f"DRY RUN: Statement {statement.reference_code} would close with penalty (paid {total_payments} < {min_required})"
                        )
                
                processed_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would process {processed_count} statements")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed {processed_count} statements: "
                    f"{no_penalty_count} without penalty, {penalty_count} with penalty"
                )
            )
