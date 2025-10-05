# kyc/api/public/v1/views/video_verification.py

import os
import tempfile
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from kyc.services.identity_auth_service import get_identity_auth_service
from kyc.api.public.v1.serializers.video_verification import (
    VideoVerificationSubmitSerializer,
    VideoVerificationPollSerializer
)
from kyc.api.public.v1.permissions import IsIdentityVerified


class VideoVerificationSubmitView(APIView):
    """
    API view for submitting video identity verification requests.
    """
    permission_classes = [IsAuthenticated, IsIdentityVerified]
    
    def post(self, request):
        """
        Submit video for identity verification.
        
        Expected payload:
        {
            "national_id": "1234567890",
            "birth_date": "1370/01/01",
            "selfie_video": <video_file>,
            "rand_action": "action_string",
            "matching_thr": 80,
            "liveness_thr": 80
        }
        """
        serializer = VideoVerificationSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation error',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get identity auth service
            auth_service = get_identity_auth_service()
            
            # Save video file temporarily
            video_file = request.FILES.get('selfie_video')
            if not video_file:
                return Response({
                    'success': False,
                    'message': 'Selfie video file is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create a temporary file to store the video
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(video_file.name)[1]
            ) as tmp_file:
                for chunk in video_file.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name
            
            try:
                # Submit video for verification
                result = auth_service.verify_idcard_video(
                    national_code=serializer.validated_data['national_id'],
                    birth_date=serializer.validated_data['birth_date'],
                    selfie_video_path=tmp_file_path,
                    rand_action=serializer.validated_data['rand_action'],
                    matching_thr=serializer.validated_data.get('matching_thr'),
                    liveness_thr=serializer.validated_data.get('liveness_thr')
                )
                
                if result.get('success'):
                    return Response({
                        'success': True,
                        'message': 'Video verification submitted successfully',
                        'data': result.get('data', {})
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'message': 'Video verification submission failed',
                        'error': result.get('error'),
                        'status': result.get('status')
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': 'An unexpected error occurred',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VideoVerificationPollView(APIView):
    """
    API view for polling video identity verification results.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Poll for video verification result.
        
        Expected payload:
        {
            "unique_id": "verification_unique_id"
        }
        """
        serializer = VideoVerificationPollSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation error',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get identity auth service
            auth_service = get_identity_auth_service()
            
            # Poll for verification result
            result = auth_service.get_video_verification_result(
                serializer.validated_data['unique_id']
            )
            
            if result.get('success'):
                return Response({
                    'success': True,
                    'message': 'Video verification result retrieved',
                    'data': {
                        'matching': result.get('matching'),
                        'liveness': result.get('liveness'),
                        'spoofing': result.get('spoofing'),
                        'raw': result.get('raw')
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'Could not retrieve video verification result',
                    'error': result.get('error'),
                    'status': result.get('status')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': 'An unexpected error occurred',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
