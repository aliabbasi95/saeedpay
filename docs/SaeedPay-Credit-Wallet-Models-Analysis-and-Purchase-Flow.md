# SaeedPay Credit & Wallet Models Analysis and Purchase Flow Documentation

## Overview

This document provides a comprehensive analysis of the SaeedPay credit provider application's model architecture, focusing on the separation of concerns between credit and wallet models, and documenting the complete purchase-and-payment workflow.

## Model Architecture Analysis

### Credit Models (`/credit/models/`)

The credit system consists of three core models that handle credit-specific business logic:

#### 1. CreditLimit Model

- **Purpose**: Manages user credit limits, usage tracking, and availability
- **Key Methods**:
  - `use_credit(amount)` - Atomically consume credit for purchases
  - `release_credit(amount)` - Atomically release credit on payments
  - `available_limit` property - Calculate remaining credit dynamically
- **Business Logic**: Credit limit management with status tracking and expiry handling

#### 2. Statement Model

- **Purpose**: Monthly billing statements with Persian (Jalali) calendar support
- **Key Methods**:
  - `close_statement()` - Month-end processing and status transitions
  - `add_transaction(transaction)` - Record credit purchases
  - `apply_payment(amount, transaction)` - Process statement payments
  - `calculate_penalty()` - Late payment penalty calculations
  - `calculate_minimum_payment_amount()` - Minimum payment logic
  - `process_payment_during_grace_period()` - Grace period outcome determination
- **Business Logic**: Complete billing cycle management with penalty and interest calculations

#### 3. StatementLine Model

- **Purpose**: Individual transaction records within statements for audit trail
- **Key Methods**: Basic CRUD with automatic parent statement balance updates
- **Business Logic**: Detailed transaction history with automatic balance synchronization

### Wallet Models (`/wallets/models/`)

The wallet system handles digital wallet operations and payment processing:

#### 1. Wallet Model

- **Purpose**: Digital wallet balance management
- **Key Methods**:
  - `available_balance` property - Calculate spendable balance (balance - reserved)
  - `save()` - Auto-generate unique wallet numbers
- **Business Logic**: Multi-wallet support per user with different types and owners

#### 2. Transaction Model

- **Purpose**: Wallet-to-wallet transfers and transaction recording
- **Key Methods**: Reference code generation and status tracking
- **Business Logic**: Complete transaction audit trail with status management

#### 3. PaymentRequest Model

- **Purpose**: Payment processing workflow management
- **Key Methods**:
  - `mark_awaiting_merchant()` - Set awaiting confirmation status
  - `mark_completed()` - Finalize successful payments
  - `mark_cancelled()` / `mark_expired()` - Handle failed payments with rollback
- **Business Logic**: Payment lifecycle management with merchant confirmation flow

#### 4. InstallmentPlan & Installment Models

- **Purpose**: Installment payment plans and individual installment tracking
- **Key Methods**:
  - `calculate_penalty()` - Overdue installment penalties
  - `mark_paid()` - Record installment payments
- **Business Logic**: Flexible installment payment system with penalty calculations

#### 5. WalletTransferRequest Model

- **Purpose**: Peer-to-peer wallet transfers
- **Key Methods**: Transfer request lifecycle management
- **Business Logic**: P2P transfer workflow with confirmation and expiry

## Duplication Analysis

### ✅ No Significant Duplication Found

The models demonstrate excellent separation of concerns with no problematic duplication:

**Clear Responsibilities:**

- **Credit Models**: Credit limits, monthly statements, billing cycles, Persian calendar integration
- **Wallet Models**: Digital wallet management, P2P transfers, payment processing, installment plans

**Acceptable Patterns:**

- Similar reference code generation across models (standard pattern)
- Consistent status management approaches (good architecture)
- Atomic operations and database constraints (best practices)

**Proper Integration Points:**

- Credit purchases create `Transaction` records that link to `StatementLine` entries
- Credit payments use wallet services but update credit models appropriately
- Both systems maintain consistent audit trails

## Complete Purchase-and-Payment Flow Walkthrough

### Phase 1: Credit Purchase Flow

#### Step 1: User Selects Product

- **UI Action**: User browses store, adds items to cart, clicks "Pay with Credit"
- **Backend**: Product catalog handled by Store models (outside scope)

#### Step 2: Credit Availability Check

- **UI Action**: System validates credit availability before allowing purchase
- **Model**: `CreditLimit.objects.get_user_credit_limit(user)`
- **Method**: `CreditLimit.available_limit` property
- **Logic**: Calculates `approved_limit - used_limit`
- **Database**: Read operation on `credit_creditlimit` table

#### Step 3: Create Payment Request

- **UI Action**: User confirms purchase amount and payment method
- **Model**: `PaymentRequest` created via `wallets.services.payment.create_payment_request()`
- **Method**: `PaymentRequest.save()` - generates unique reference code and sets expiry
- **Database**: Insert into `wallets_paymentrequest` table

#### Step 4: Process Credit Purchase

- **UI Action**: User confirms payment with credit
- **Model Chain**:
  1. `Statement.objects.get_or_create_current_statement(user)` - Get/create current statement
  2. `Statement.add_transaction(transaction)` - Process the purchase
  3. `CreditLimit.use_credit(amount)` - Atomically consume credit
  4. `Statement.add_line("purchase", -amount, transaction)` - Record purchase line
- **Database**:
  - Update `credit_creditlimit.used_limit`
  - Insert into `credit_statementline`
  - Update `credit_statement` balances

#### Step 5: Transaction Recording

- **UI Action**: User receives purchase confirmation with reference codes
- **Model**: `Transaction` created with SUCCESS status
- **Method**: `Transaction.save()` - generates unique reference code
- **Database**: Insert into `wallets_transaction` table
- **Result**: Purchase recorded in both wallet and credit systems with full audit trail

### Phase 2: Monthly Statement Processing

#### Step 6: Month-End Processing (Automated)

- **UI Action**: Background process (no user interaction)
- **Model**: `Statement.objects.close_monthly_statements()` - Management command
- **Method Chain**:
  1. `Statement.close_statement()` - Close current statements from previous months
  2. `Statement.update_balances()` - Finalize closing balances
  3. Set due date based on `Statement.get_due_days()` (per-user or default)
  4. Create new current statement with interest if debt exists
- **Database**:
  - Update `credit_statement.status` to "pending_payment"
  - Insert new current statements
  - Insert interest charges as `StatementLine` records

### Phase 3: Payment Flow

#### Step 7: User Views Statement

- **UI Action**: User opens app, sees pending statement notification
- **Model**: `Statement.objects.filter(user=user, status="pending_payment")`
- **Method**: `Statement.calculate_minimum_payment_amount()`
- **Display Data**:
  - Total debt amount (`closing_balance`)
  - Minimum payment required
  - Due date
  - Grace period information
- **Database**: Read from `credit_statement` and related `credit_statementline`

#### Step 8: User Initiates Payment

- **UI Action**: User selects payment amount and source wallet
- **Model**: `Wallet.objects.get(user=user, kind="personal")`
- **Method**: `Wallet.available_balance` property validation
- **Validation**: Ensures sufficient wallet balance for payment
- **Database**: Read from `wallets_wallet` table

#### Step 9: Process Statement Payment

- **UI Action**: User confirms payment transaction
- **Model**: `Statement.apply_payment(amount, transaction)`
- **Method Chain**:
  1. `Statement.add_line("payment", amount, transaction)` - Record payment line
  2. `CreditLimit.release_credit(amount)` - Free up credit limit atomically
  3. `StatementLine.save()` - Triggers `Statement.update_balances()`
- **Database**:
  - Insert into `credit_statementline`
  - Update `credit_creditlimit.used_limit` (decrease)
  - Update `credit_statement` balances
  - Update `wallets_wallet.balance` (decrease)

#### Step 10: Payment Outcome Processing

- **UI Action**: System processes payment during grace period (background)
- **Model**: Management command calls `Statement.process_payment_during_grace_period(payment_amount)`
- **Method Logic**:
  - If `payment_amount >= minimum_payment`: `status = "closed_no_penalty"`
  - If `payment_amount < minimum_payment`: `status = "closed_with_penalty"`
  - If `debt_amount < MINIMUM_PAYMENT_THRESHOLD`: `status = "closed_no_penalty"`
- **Database**: Update `credit_statement.status` and `closed_at` timestamp

#### Step 11: Penalty Application (If Applicable)

- **UI Action**: Background process for penalty enforcement
- **Model**: `Statement.apply_penalty_to_current_statement(penalty_amount)`
- **Method**: Adds penalty to user's current statement as new `StatementLine`
- **Database**: Insert penalty record into `credit_statementline` for current statement

### Phase 4: Transaction Completion

#### Step 12: Final Balance Updates and Reconciliation

- **UI Action**: User sees updated balances and statement status in app
- **Final State**:
  - `Wallet.balance` reduced by payment amount
  - `CreditLimit.used_limit` reduced by payment amount
  - `Statement.status` updated to final state ("closed_no_penalty" or "closed_with_penalty")
  - Complete audit trail via `StatementLine` records
- **Database**: All tables synchronized with consistent balances

## Key Model Interactions Summary

| **User Action** | **Primary Model** | **Key Method** | **Secondary Models** | **Database Operations** |
|-----------------|-------------------|----------------|---------------------|------------------------|
| Check Credit | `CreditLimit` | `available_limit` | - | READ credit_creditlimit |
| Make Purchase | `Statement` | `add_transaction()` | `CreditLimit`, `StatementLine`, `Transaction` | UPDATE creditlimit, INSERT statementline, INSERT transaction |
| Month-End | `Statement` | `close_statement()` | `StatementLine` | UPDATE statement status, INSERT new statements |
| View Statement | `Statement` | `calculate_minimum_payment_amount()` | - | READ statement + lines |
| Make Payment | `Statement` | `apply_payment()` | `CreditLimit`, `StatementLine`, `Wallet` | INSERT statementline, UPDATE creditlimit, UPDATE wallet |
| Process Grace Period | `Statement` | `process_payment_during_grace_period()` | - | UPDATE statement status |

## Architecture Quality Assessment

### ✅ Strengths

1. **Clear Separation of Concerns**: Credit and wallet models handle distinct business domains
2. **Atomic Operations**: All critical operations use database transactions for consistency
3. **Comprehensive Audit Trail**: Complete transaction history across both systems
4. **Persian Calendar Integration**: Proper localization for Iranian market requirements
5. **Flexible Payment Processing**: Supports various payment scenarios and outcomes
6. **Proper Foreign Key Relationships**: Well-designed database schema with referential integrity
7. **Status Management**: Clear state machines for all business processes

### 🔧 Potential Improvements

1. **Method Consolidation**: Some penalty/fee methods could be merged for simplicity
2. **Performance Optimization**: Consider caching for frequently accessed calculations
3. **Configuration Management**: Some hardcoded values could be made configurable
4. **Error Handling**: Could benefit from more specific exception types

## Conclusion

The SaeedPay credit and wallet model architecture demonstrates **production-ready design** with:

- **No problematic duplication** between credit and wallet systems
- **Clear business logic flow** from UI interactions to database writes
- **Proper integration patterns** maintaining data consistency
- **Comprehensive feature coverage** for a complete credit provider application

The system successfully handles the complete lifecycle of credit operations while maintaining clean separation between wallet and credit concerns. The Persian calendar integration and flexible payment processing make it well-suited for the Iranian market.
