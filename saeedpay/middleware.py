# saeedpay/middleware.py

import uuid

from django.conf import settings

from saeedpay.logging import reset_request_id, set_request_id


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.header_name = getattr(settings, "REQUEST_ID_HEADER", "X-Request-ID")

    def __call__(self, request):
        incoming_request_id = request.headers.get(self.header_name)
        request_id = incoming_request_id or str(uuid.uuid4())

        request.request_id = request_id
        token = set_request_id(request_id)

        try:
            response = self.get_response(request)
        except Exception:
            reset_request_id(token)
            raise

        response[self.header_name] = request_id
        reset_request_id(token)
        return response
