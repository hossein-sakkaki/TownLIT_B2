from rest_framework import serializers
from django.utils import timezone 

from .models import Store, ServiceCategory
from apps.accounts.serializers import AddressSerializer
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer


 # SERVICE CATEGORY Serializer -----------------------------------------------------------------------
class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = '__all__'

        
# STORE Serializer ---------------------------------------------------------------------------------
class StoreSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    store_address = AddressSerializer(read_only=True)
    service_categories = ServiceCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Store
        fields = [
            'id', 'organization', 'custom_service_name', 'description', 'store_logo', 'store_phone_number',
            'store_address', 'url_links', 'service_categories', 'currency_preference', 'license_number',
            'license_expiry_date', 'tax_id', 'store_license', 'sales_report', 'revenue',
            'register_date', 'active_date', 'is_restricted', 'is_verified', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'register_date', 'slug', 'active_date', 'is_verified', 'is_active']

    def validate_store_phone_number(self, value):
        if not value.isdigit() or len(value) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits and numeric.")
        return value

    def validate_license_expiry_date(self, value):
        if value and value < timezone.now().date():
            raise serializers.ValidationError("License expiry date cannot be in the past.")
        return value

    def validate_revenue(self, value):
        if value and value < 0:
            raise serializers.ValidationError("Revenue cannot be negative.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('license_number'):
            raise serializers.ValidationError("Active store must have a license number.")
        return data