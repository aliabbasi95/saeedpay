# credit/tests/test_statement_api_optimization.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.models.credit_limit import CreditLimit
from persiantools.jdatetime import JalaliDate

User = get_user_model()


class StatementAPIOptimizationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create a credit limit for the user
        self.credit_limit = CreditLimit.objects.create(
            user=self.user,
            approved_limit=1000000,
            available_limit=1000000,
            used_limit=0,
            status='active'
        )
        
        # Create test statements
        jtoday = JalaliDate.today()
        self.statement1 = Statement.objects.create(
            user=self.user,
            year=jtoday.year,
            month=jtoday.month,
            status='current',
            opening_balance=0,
            closing_balance=50000,
            total_debit=100000,
            total_credit=50000
        )
        
        self.statement2 = Statement.objects.create(
            user=self.user,
            year=jtoday.year,
            month=jtoday.month - 1 if jtoday.month > 1 else 12,
            status='closed_no_penalty',
            opening_balance=0,
            closing_balance=0,
            total_debit=75000,
            total_credit=75000
        )
        
        # Create statement lines for statement1
        StatementLine.objects.create(
            statement=self.statement1,
            type='purchase',
            amount=50000,
            description='Test purchase'
        )
        StatementLine.objects.create(
            statement=self.statement1,
            type='payment',
            amount=-25000,
            description='Test payment'
        )

    def test_statement_list_excludes_lines(self):
        """Test that statement list endpoint excludes lines field"""
        url = reverse('credit:statement-list')  # Adjust URL name as needed
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        
        if response.data:
            statement_data = response.data[0]
            # Should NOT include lines field
            self.assertNotIn('lines', statement_data)
            # Should NOT include paid_at and closed_at fields
            self.assertNotIn('paid_at', statement_data)
            self.assertNotIn('closed_at', statement_data)
            
            # Should include essential fields
            expected_fields = {
                'id', 'user', 'year', 'month', 'reference_code', 'status',
                'opening_balance', 'closing_balance', 'total_debit', 'total_credit',
                'grace_date', 'created_at', 'updated_at'
            }
            for field in expected_fields:
                self.assertIn(field, statement_data, f"Field {field} should be present in list view")

    def test_statement_detail_includes_lines(self):
        """Test that statement detail endpoint includes lines field"""
        url = reverse('credit:statement-detail', kwargs={'pk': self.statement1.pk})  # Adjust URL name as needed
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        statement_data = response.data
        # Should include lines field
        self.assertIn('lines', statement_data)
        self.assertIsInstance(statement_data['lines'], list)
        self.assertEqual(len(statement_data['lines']), 2)  # We created 2 lines
        
        # Should include all fields including paid_at and closed_at
        expected_fields = {
            'id', 'user', 'year', 'month', 'reference_code', 'status',
            'opening_balance', 'closing_balance', 'total_debit', 'total_credit',
            'grace_date', 'paid_at', 'closed_at', 'lines', 'created_at', 'updated_at'
        }
        for field in expected_fields:
            self.assertIn(field, statement_data, f"Field {field} should be present in detail view")
        
        # Verify line structure
        line_data = statement_data['lines'][0]
        expected_line_fields = {'id', 'statement', 'type', 'amount', 'transaction', 'created_at', 'description'}
        for field in expected_line_fields:
            self.assertIn(field, line_data, f"Field {field} should be present in line data")

    def test_statement_line_list_filtering(self):
        """Test that statement line list supports filtering by statement_id"""
        url = reverse('credit:statement-line-list')  # Adjust URL name as needed
        
        # Test without filtering
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Should return all lines for user
        
        # Test with statement_id filtering
        response = self.client.get(url, {'statement_id': self.statement1.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Should return lines for statement1
        
        # Test with non-existent statement_id
        response = self.client.get(url, {'statement_id': 99999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)  # Should return no lines

    def test_statement_list_ordering(self):
        """Test that statement list is ordered by most recent first"""
        url = reverse('credit:statement-list')  # Adjust URL name as needed
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)
        
        # First statement should be the more recent one (statement1)
        first_statement = response.data[0]
        self.assertEqual(first_statement['id'], self.statement1.id)
