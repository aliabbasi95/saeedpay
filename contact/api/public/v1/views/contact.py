from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from contact.api.public.v1.serializers.contact import ContactCreateSerializer
from contact.api.public.v1.schema import contact_create_schema
from rest_framework.permissions import AllowAny

class ContactCreateView(APIView):
    permission_classes = [AllowAny]
    
    @contact_create_schema
    def post(self, request, *args, **kwargs):

        serializer = ContactCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

