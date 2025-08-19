import os
from pathlib import Path
from .admin_reorder import ADMIN_REORDER

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = os.environ['SECRET_KEY']
SECRET_KEY = '123456'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []
CSRF_TRUSTED_ORIGINS = []

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
REDIS_PASSWORD=''

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

CAS_PUBLICKEY_URL = 'http://erp.ag/cas/static/public_key.pem'
CAS_URL = 'http://erp.ag/cas'
CAS_DEBUG = False
CAS_SAME_ORIGIN=True

KAVENEGAR_API_KEY = '5130593D'
KAVENEGAR_NUMBER = ''

CAS_TOKEN = '123123j1oi2j3io1'

FRONTEND_BASE_URL = "http://172.20.20.134:3000/"

LLM_BASE_URL = 'http://192.168.20.250:8008/'

CHATBOT_HISTORY_LIMIT = 4
CHATBOT_SESSION_LIMIT = 2
# Card Validator Configuration
CARD_VALIDATOR_MOCK = True  # Set to False for production validation
