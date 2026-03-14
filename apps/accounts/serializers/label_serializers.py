# apps/accounts/serializers/label_serializers.py

from rest_framework import serializers
from ..models import CustomLabel


class CustomLabelSerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomLabel
        fields = "__all__"