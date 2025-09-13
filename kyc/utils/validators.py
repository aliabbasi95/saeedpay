# kyc/utils/validators.py

import re
from typing import Dict, Any, Optional
from django.core.exceptions import ValidationError


def validate_national_id(national_id: str) -> bool:
    """
    Validate Iranian national ID format.
    
    Args:
        national_id: National ID string to validate
        
    Returns:
        bool: True if valid format, False otherwise
    """
    if not national_id or not isinstance(national_id, str):
        return False
    
    # Remove any non-digit characters
    clean_id = re.sub(r'\D', '', national_id)
    
    # Check length (should be 10 digits)
    if len(clean_id) != 10:
        return False
    
    # Check if all digits are the same (invalid)
    if len(set(clean_id)) == 1:
        return False
    
    # Iranian national ID validation algorithm
    try:
        digits = [int(d) for d in clean_id]
        
        # Calculate check digit
        sum_val = 0
        for i in range(9):
            sum_val += digits[i] * (10 - i)
        
        remainder = sum_val % 11
        check_digit = 11 - remainder if remainder >= 2 else remainder
        
        return check_digit == digits[9]
    except (ValueError, IndexError):
        return False


def validate_phone_number(phone: str) -> bool:
    """
    Validate Iranian phone number format.
    
    Args:
        phone: Phone number string to validate
        
    Returns:
        bool: True if valid format, False otherwise
    """
    if not phone or not isinstance(phone, str):
        return False
    
    # Remove any non-digit characters
    clean_phone = re.sub(r'\D', '', phone)
    
    # Check if it starts with 09 and has 11 digits total
    if len(clean_phone) == 11 and clean_phone.startswith('09'):
        return True
    
    # Check if it starts with +98 and has 13 digits total
    if len(clean_phone) == 13 and clean_phone.startswith('98'):
        return True
    
    return False


def validate_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate user data for identity verification.
    
    Args:
        user_data: Dictionary containing user information
        
    Returns:
        Dict containing validation result and cleaned data
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(user_data, dict):
        raise ValidationError("User data must be a dictionary")
    
    cleaned_data = {}
    errors = {}
    
    # Validate national_id if provided
    if 'national_id' in user_data:
        national_id = str(user_data['national_id']).strip()
        if national_id:
            if validate_national_id(national_id):
                cleaned_data['national_id'] = national_id
            else:
                errors['national_id'] = 'Invalid national ID format'
        else:
            errors['national_id'] = 'National ID is required'
    
    # Validate phone if provided
    if 'phone' in user_data:
        phone = str(user_data['phone']).strip()
        if phone:
            if validate_phone_number(phone):
                cleaned_data['phone'] = phone
            else:
                errors['phone'] = 'Invalid phone number format'
        else:
            errors['phone'] = 'Phone number is required'
    
    # Validate first_name if provided
    if 'first_name' in user_data:
        first_name = str(user_data['first_name']).strip()
        if first_name:
            if len(first_name) >= 2:
                cleaned_data['first_name'] = first_name
            else:
                errors['first_name'] = 'First name must be at least 2 characters'
    
    # Validate last_name if provided
    if 'last_name' in user_data:
        last_name = str(user_data['last_name']).strip()
        if last_name:
            if len(last_name) >= 2:
                cleaned_data['last_name'] = last_name
            else:
                errors['last_name'] = 'Last name must be at least 2 characters'
    
    # Check if at least one required field is provided
    required_fields = ['national_id', 'phone']
    if not any(field in cleaned_data for field in required_fields):
        errors['general'] = 'At least one of national_id or phone must be provided'
    
    if errors:
        raise ValidationError(errors)
    
    return cleaned_data


def sanitize_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize user data by removing sensitive information and normalizing format.
    
    Args:
        user_data: Dictionary containing user information
        
    Returns:
        Dict containing sanitized data
    """
    sanitized = {}
    
    # Normalize national_id
    if 'national_id' in user_data:
        national_id = str(user_data['national_id']).strip()
        # Remove any non-digit characters
        clean_id = re.sub(r'\D', '', national_id)
        if clean_id:
            sanitized['national_id'] = clean_id
    
    # Normalize phone
    if 'phone' in user_data:
        phone = str(user_data['phone']).strip()
        # Remove any non-digit characters
        clean_phone = re.sub(r'\D', '', phone)
        if clean_phone:
            # Convert to standard format (09xxxxxxxxx)
            if clean_phone.startswith('98'):
                clean_phone = '0' + clean_phone[2:]
            elif clean_phone.startswith('9'):
                clean_phone = '0' + clean_phone
            
            if len(clean_phone) == 11 and clean_phone.startswith('09'):
                sanitized['phone'] = clean_phone
    
    # Normalize names
    for field in ['first_name', 'last_name']:
        if field in user_data:
            name = str(user_data[field]).strip()
            if name:
                # Remove extra spaces and normalize
                normalized_name = ' '.join(name.split())
                sanitized[field] = normalized_name
    
    return sanitized
