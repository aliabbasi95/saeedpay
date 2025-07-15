# SaeedPay Payment Microservice

## Overview

SaeedPay is a modular microservice-based wallet and payment system designed with security, extensibility, and best-practice Django/DRF patterns.  
It supports customer and merchant wallet operations, real-time payment requests, and a secure, double-confirmation payment flow with full auditability.

---

## Features

- **Role-Based Registration**:  
  Separate registration flows for customers and merchants, supporting OTP and password validation, profile association, and role assignment.

- **Wallet System**:  
  Each user (customer/merchant) gets default wallet(s) on registration.  
  Supports multiple wallet types: micro credit, cash, cashback, credit, merchant gateway, escrow, etc.

- **Secure Payment Flow**:  
  - Merchant creates a payment request via API key.
  - Customer reviews and confirms payment from their wallet.
  - Amount moves to the escrow wallet until merchant confirms payment.
  - After final merchant verification, funds are released to the merchant's wallet.
  - If expired or canceled, full rollback and audit trail is enforced.

- **Reference Codes**:  
  Each PaymentRequest and Transaction is assigned a unique, user-friendly reference code (e.g. `PR240712654321`, `TRX240712123456`).

- **Atomic Rollback**:  
  All payment and transfer operations are ACID-safe and will rollback on failure, with automatic handling for expired or canceled requests.

- **Admin/Staff Extensibility**:  
  Clear separation of concerns for roles, permissions, and future extensibility.

- **API-First Design**:  
  All flows are available as REST APIs with JWT/ApiKey authentication, full OpenAPI schema, and documented endpoints.

---

## Folder Structure

- `auth_api/` - Authentication, registration, OTP, and login flows.
- `customers/` - Customer-specific models and APIs.
- `merchants/` - Merchant models, API key logic, merchant-specific views.
- `profiles/` - User profile management.
- `wallets/` - Wallet logic, payment requests, transactions, core payment engine.
- `lib/` - Base models, shared validation, reusable DRF utilities.

---

## How to Run

1. **Clone the repository**

    ```bash
    git clone saeedpay
    cd saeedpay
    ```

2. **Add and initialize submodules**

    ```bash
    git submodule update --init --recursive
    ```

3. **Copy and edit local settings**

    Copy saeedpay/local_settings_template.py to saeedpay/local_settings.py and fill in your database, email, JWT secret, and other local credentials.


4. **Install requirements**

    ```bash
    pip install -r lib/rep_base/requirements.txt
    pip install -r lib/cas_auth/requirements.txt
    pip install -r requirements.txt
    ```

5. **Setup the database**

    ```bash
    python manage.py migrate
    ```

6. **Create superuser (optional, for admin)**

    ```bash
    python manage.py createsuperuser
    ```

7. **Run the server**

    ```bash
    python manage.py runserver
    ```

8. **Ensure Escrow Wallet Exists**

    On startup, the system ensures an escrow user and wallet exist for safe payment holding.

---

## Payment Flow Example

1. **Merchant Initiates Payment**

    - `POST /api/wallets/payment-request/`
    - Requires merchant API key.
    - Receives a `reference_code` and a `payment_url` for redirect.

2. **Customer Confirms Payment**

    - Visits `payment_url`, reviews, and confirms payment.
    - Payment amount moves from customer wallet to escrow.

3. **Merchant Verifies Payment**

    - Calls `POST /api/wallets/payment-request/{reference_code}/verify/` with their API key.
    - System transfers escrow funds to merchant wallet, marks transaction as `success`, and returns tracking codes.

4. **If Payment Expires or is Canceled**

    - Funds in escrow are rolled back to the customer wallet.
    - Status and audit logs updated accordingly.

---

## Testing

- **Full test coverage** using pytest.
- Separate tests for unit (models, utils), serializer, and API endpoint flows.
- Run all tests:

    ```bash
    pytest
    ```

---

## License

[MIT](LICENSE)

---
