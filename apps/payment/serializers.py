from rest_framework import serializers
from .models import PaymentSubscription, PaymentDonation, PaymentAdvertisement, PaymentInvoice, PaymentShoppingCart, Pricing
from apps.posts.serializers import SimpleOrganizationSerializer, SimpleCustomUserSerializer




# PRICING Serializer --------------------------------------------------------------------------------
class PricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pricing
        fields = ['id', 'pricing_type', 'duration', 'billing_cycle', 'price', 'discount', 'is_active']


# PAYMENT SUBSCRIPTION Serializer -------------------------------------------------------------------
class PaymentSubscriptionSerializer(serializers.ModelSerializer):
    subscription_pricing = PricingSerializer()
    user = SimpleCustomUserSerializer(read_only=True)
    organization = SimpleOrganizationSerializer(read_only=True)

    class Meta:
        model = PaymentSubscription
        fields = ['id', 'user', 'organization', 'amount', 'payment_status', 'created_at', 'updated_at', 'description',
                  'reference_number', 'subscription_pricing', 'start_date', 'end_date', 'is_active']
        read_only_fields = ['id', 'created_at', 'updated_at', 'reference_number']


# PAYMENT ADVERTISEMENT Serializer ------------------------------------------------------------------
class PaymentAdvertisementSerializer(serializers.ModelSerializer):
    advertisement_pricing = PricingSerializer()
    user = SimpleCustomUserSerializer(read_only=True)
    organization = SimpleOrganizationSerializer(read_only=True)

    class Meta:
        model = PaymentAdvertisement
        fields = ['id', 'user', 'organization', 'amount', 'payment_status', 'created_at', 'updated_at', 'description',
                  'reference_number', 'advertisement_pricing', 'start_date', 'end_date']
        read_only_fields = ['id', 'created_at', 'updated_at', 'reference_number']


# PAYMENT DONATION Serializer -----------------------------------------------------------------------
class PaymentDonationSerializer(serializers.ModelSerializer):
    user = SimpleCustomUserSerializer(read_only=True)
    organization = SimpleOrganizationSerializer(read_only=True)

    class Meta:
        model = PaymentDonation
        fields = ['id', 'user', 'organization', 'amount', 'payment_status', 'created_at', 'updated_at', 'description',
                  'reference_number', 'message']
        read_only_fields = ['id', 'created_at', 'updated_at', 'reference_number']


# PAYMENT SHOPPING CART SERIALIZER ---------------------------------------------------------
class PaymentShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentShoppingCart
        fields = [ 'id', 'user', 'organization', 'amount', 'payment_status', 'created_at', 'updated_at', 'description',
                'reference_number', 'shopping_cart', 'billing_address']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'reference_number']

    def validate(self, data):
        # Ensure that the amount is positive
        if 'amount' in data and data['amount'] <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return data
        
        
# PAYMENT INVOICE Serializer ------------------------------------------------------------------------
class PaymentInvoiceSerializer(serializers.ModelSerializer):
    payment = serializers.PrimaryKeyRelatedField(queryset=PaymentSubscription.objects.all())

    class Meta:
        model = PaymentInvoice
        fields = ['id', 'payment', 'invoice_number', 'issued_date', 'due_date', 'is_paid']
        read_only_fields = ['id', 'invoice_number', 'issued_date']
