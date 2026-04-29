from rest_framework import serializers


def https_only_validator(value):
    if not str(value).startswith("https://"):
        raise serializers.ValidationError("URL must start with https://")
