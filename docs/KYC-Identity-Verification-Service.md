# KYC Identity Verification Service

This document describes the KYC (Know Your Customer) app that handles user identity verification and authentication with external KYC providers.

## Features

- **Identity Authentication Service**: Manages access and refresh tokens for external KYC providers
- **User Data Validation**: Validates Iranian national ID, phone numbers, and other user data
- **Token Management**: Automatic token refresh and caching
- **Error Handling**: Comprehensive error handling and logging

## Configuration

### 1. Environment Variables

Add the following to your `.env` file:

```bash
# KYC Identity Service Credentials
KIAHOOSHAN_USERNAME=your_username
KIAHOOSHAN_PASSWORD=your_password
```

### 2. Django Settings

Add the following settings to your Django settings file:

```python
# KYC Identity Service Configuration
KYC_IDENTITY_BASE_URL = 'https://your-kyc-provider.com/api'
KYC_IDENTITY_TIMEOUT = 30  # seconds, optional, defaults to 30
```

## Usage

### Basic Usage

```python
from kyc.services import get_identity_auth_service

# Get the service instance
auth_service = get_identity_auth_service()

# Verify user identity
user_data = {
    'national_id': '1234567890',
    'phone': '09123456789',
    'first_name': 'علی',
    'last_name': 'احمدی'
}

result = auth_service.verify_identity(user_data)
if result['success']:
    print("Identity verified successfully")
else:
    print(f"Verification failed: {result['error']}")
```

### Advanced Usage

```python
from kyc.services import IdentityAuthService
from kyc.utils import validate_user_data, sanitize_user_data

# Create service instance
service = IdentityAuthService()

# Validate and sanitize user data
try:
    validated_data = validate_user_data(user_data)
    sanitized_data = sanitize_user_data(validated_data)
    
    # Verify identity
    result = service.verify_identity(sanitized_data)
    
except ValidationError as e:
    print(f"Validation error: {e}")
```

### Using in Other Apps

```python
# In any other app (e.g., auth_api, profiles, etc.)
from kyc.services import get_identity_auth_service

def verify_user_identity(user_data):
    auth_service = get_identity_auth_service()
    return auth_service.verify_identity(user_data)
```

## API Endpoints

The service expects the following endpoints from your KYC provider:

- `POST /auth/login` - Authentication endpoint
- `POST /auth/refresh` - Token refresh endpoint  
- `POST /verify/identity` - Identity verification endpoint

## Error Handling

The service provides comprehensive error handling:

- **AUTH_FAILED**: Authentication with identity service failed
- **VERIFICATION_FAILED**: Identity verification request failed
- **UNEXPECTED_ERROR**: An unexpected error occurred
- **INVALID_CONFIG**: KYC Identity service configuration is invalid
- **TOKEN_EXPIRED**: Access token has expired
- **REFRESH_FAILED**: Token refresh failed

## Token Management

The service automatically handles:

- Token caching using Django's cache framework
- Automatic token refresh when access token expires
- Re-authentication when refresh fails
- Token cleanup and cache management

## Validation

The app includes validators for:

- Iranian national ID format validation
- Iranian phone number format validation
- User data validation and sanitization
- Input format normalization

## Logging

All operations are logged using Django's logging framework. Set the log level for the `kyc` logger to control verbosity.
