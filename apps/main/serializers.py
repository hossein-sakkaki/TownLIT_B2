from rest_framework import serializers
from rest_framework import serializers
from .models import TermsAndPolicy, UserAgreement, PolicyChangeHistory, FAQ, UserFeedback, SiteAnnouncement, UserActionLog



# TERMS AND POLICY Serializer ---------------------------------------------------------------------------------
class TermsAndPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsAndPolicy
        fields = '__all__'


# USER AGREEMENT Serializer -----------------------------------------------------------------------------------
class UserAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAgreement
        fields = '__all__'


# POLICY CHANGE HISTORY Serializer ----------------------------------------------------------------------------
class PolicyChangeHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyChangeHistory
        fields = '__all__'


# FAQ Serializer ----------------------------------------------------------------------------------------------
class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = '__all__'


# USER FEEDBACK Serializer ------------------------------------------------------------------------------------
class UserFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFeedback
        fields = '__all__'


# SITE ANNOUNCEMENT Serializer --------------------------------------------------------------------------------
class SiteAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteAnnouncement
        fields = '__all__'


# USER ACTION LOG Serializer ----------------------------------------------------------------------------------
class UserActionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActionLog
        fields = '__all__'