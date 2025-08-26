import requests
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from functools import wraps


def verify_recaptcha(token: str, action: str | None = None):
    """
    Raises ValidationError on any failure.
    `action` required only for v3.
    """
    url = 'https://www.google.com/recaptcha/api/siteverify'
    payload = {
        'secret': settings.RECAPTCHA_SECRET_KEY,
        'response': token,
    }
    try:
        r = requests.post(url, data=payload, timeout=5, proxies={
            'http': 'http://127.0.0.1:20171',
            'all': 'socks5://127.0.0.1:20170',
            'https': 'http://127.0.0.1:20172',
        }).json()
    except requests.RequestException:
        raise ValidationError('Captcha verification service unavailable.')

    if not r.get('success'):
        raise ValidationError(f'{r}Captcha verification failed.')

    if settings.RECAPTCHA_V3:
        if action and r.get('action') != action:
            raise ValidationError('Captcha action mismatch.')
        score = float(r.get('score', 0))
        if score < settings.RECAPTCHA_V3_THRESHOLD:
            raise ValidationError('Captcha score too low.')


class ReCaptchaField(serializers.CharField):
    """
    Serializer field that validates a reCAPTCHA token.
    Usage:
        token = ReCaptchaField(action='submit')  # action only for v3
    """
    def __init__(self, *, action=None, **kwargs):
        self.action = action
        kwargs.setdefault('write_only', True)
        kwargs.setdefault('required', True)
        super().__init__(**kwargs)

    def run_validation(self, data):
        # When using source, `data` is the value of the source field.
        # However, to be more robust, we check the initial data directly.
        token = self.parent.initial_data.get('g-recaptcha-response')
        if not token:
            raise ValidationError('The reCAPTCHA token (g-recaptcha-response) is missing.')
        verify_recaptcha(token, action=self.action)
        return data


class ReCaptchaMixin:
    """
    Mixin for GenericAPIView / ViewSet.
    Define on the class:
        recaptcha_actions = {'create', 'like'}   # any DRF action names
        recaptcha_action_name = 'submit'         # v3 action string (optional)
    """
    recaptcha_actions = {'create'}
    recaptcha_action_name = None

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if hasattr(self, 'action') and self.action in self.recaptcha_actions:
            # Dynamically inject the field only for those actions
            serializer.fields['recaptcha_token'] = ReCaptchaField(
                source='g-recaptcha-response',
                action=self.recaptcha_action_name,
                required=True
            )

            # Wrap the serializer's create method to remove the recaptcha field
            # before it's passed to the model's create method.
            original_create = serializer.create

            def wrapped_create(self, validated_data):
                validated_data.pop('g-recaptcha-response', None)
                return original_create(validated_data)

            import types
            serializer.create = types.MethodType(wrapped_create, serializer)
        return serializer


def recaptcha_required(*actions, action_name=None):
    """
    Class decorator for DRF views / viewsets.
    Example:
        @recaptcha_required('create', 'like', action_name='submit')
        class CommentViewSet(ModelViewSet): ...
    """
    def decorator(cls):
        cls.recaptcha_actions = set(actions)
        cls.recaptcha_action_name = action_name
        # Inject the mixin
        if ReCaptchaMixin not in cls.__bases__:
            cls.__bases__ = (ReCaptchaMixin,) + cls.__bases__
        return cls
    return decorator
