# kyc/api/public/v1/views/identity_verification.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError

from kyc.services import get_identity_auth_service
from kyc.utils import validate_user_data, sanitize_user_data


class IdentityVerificationView(APIView):
    """
    API view for identity verification using external KYC service.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Verify user identity.
        
        Expected payload:
        {
            "national_id": "1234567890",
            "phone": "09123456789",
            "first_name": "علی",
            "last_name": "احمدی"
        }
        """
        try:
            # Validate and sanitize input data
            validated_data = validate_user_data(request.data)
            sanitized_data = sanitize_user_data(validated_data)
            
            # Get identity auth service
            auth_service = get_identity_auth_service()
            
            # Verify identity
            result = auth_service.verify_identity(sanitized_data)
            
            if result.get('success'):
                return Response({
                    'success': True,
                    'message': 'Identity verified successfully',
                    'data': result.get('data', {})
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'Identity verification failed',
                    'error': result.get('error'),
                    'error_code': result.get('error_code')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except ValidationError as e:
            return Response({
                'success': False,
                'message': 'Validation error',
                'errors': e.message_dict if hasattr(e, 'message_dict') else str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': 'An unexpected error occurred',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
