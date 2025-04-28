from rest_framework import serializers
from django.db.models import Q
from django.utils import timezone 
from django.core.validators import RegexValidator
from .models import (
                Friendship, Fellowship, MemberServiceType,AcademicRecord,
                Member, GuestUser,
                ClientRequest, Client, Customer, MigrationHistory,
                SpiritualGift, SpiritualGiftSurveyQuestion, SpiritualGiftSurveyResponse, MemberSpiritualGifts
            )
from apps.profilesOrg.serializers import OrganizationSerializer
from apps.posts.serializers import SimpleOrganizationSerializer, SimpleCustomUserSerializer
from apps.accounts.serializers import (
                                AddressSerializer, SpiritualServiceSerializer,
                                CustomUserSerializer, PublicCustomUserSerializer, LimitedCustomUserSerializer, 
                                SimpleCustomUserSerializer, SpiritualServiceSerializer
                            )
from apps.config.profiles_constants import FRIENDSHIP_STATUS_CHOICES, FELLOWSHIP_RELATIONSHIP_CHOICES, RECIPROCAL_FELLOWSHIP_CHOICES, RECIPROCAL_FELLOWSHIP_MAP
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# FRIENDSHIP Serializer ---------------------------------------------------------------
class FriendshipSerializer(serializers.ModelSerializer):
    from_user = SimpleCustomUserSerializer(read_only=True)
    to_user = SimpleCustomUserSerializer(read_only=True)
    to_user_id = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), write_only=True)

    class Meta:
        model = Friendship
        fields = ['id', 'from_user', 'to_user', 'to_user_id', 'created_at', 'status', 'deleted_at', 'is_active']
        read_only_fields = ['from_user', 'to_user', 'created_at', 'deleted_at']

    def validate_to_user_id(self, value):
        # Ensures that a user cannot send a friend request to themselves
        if self.context['request'].user == value:
            raise serializers.ValidationError("You cannot send a friend request to yourself.")
        return value

    def validate_status(self, value):
        # Checks if the status is valid
        valid_statuses = [choice[0] for choice in FRIENDSHIP_STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError("Invalid status for friendship.")
        return value

    def create(self, validated_data):
        from_user = self.context['request'].user
        to_user = validated_data.pop('to_user_id')

        # Check for existing active requests
        existing_request = Friendship.objects.filter(
            from_user=from_user,
            to_user=to_user,
            is_active=True
        ).exclude(status='declined')

        if existing_request.exists():
            raise serializers.ValidationError("Friendship request already exists.")

        validated_data.pop('from_user', None)
        validated_data.pop('to_user', None)
        return Friendship.objects.create(
            from_user=from_user,
            to_user=to_user,
            **validated_data
        )


# FELLOWSHIP Serializer ---------------------------------------------------------------
class FellowshipSerializer(serializers.ModelSerializer):
    from_user = SimpleCustomUserSerializer(read_only=True)
    to_user = SimpleCustomUserSerializer(read_only=True)
    to_user_id = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), write_only=True)
    reciprocal_fellowship_type = serializers.CharField(required=False)

    class Meta:
        model = Fellowship
        fields = [
            'id', 'from_user', 'to_user', 'to_user_id', 'fellowship_type', 'reciprocal_fellowship_type', 'status', 'created_at',
        ]
        read_only_fields = ['from_user', 'to_user', 'created_at', 'reciprocal_fellowship_type']

    def validate_to_user_id(self, value):
        if self.context['request'].user == value:
            raise serializers.ValidationError("You cannot send a request to yourself.")
        return value

    def validate_fellowship_type(self, value):
        valid_types = [choice[0] for choice in FELLOWSHIP_RELATIONSHIP_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError("Invalid fellowship type.")
        return value

    def validate_reciprocal_fellowship_type(self, value):
        if value:
            valid_types = [choice[0] for choice in RECIPROCAL_FELLOWSHIP_CHOICES]
            if value not in valid_types:
                raise serializers.ValidationError("Invalid reciprocal fellowship type.")
        return value

    def validate(self, data):
        from_user = self.context['request'].user
        to_user = data.get('to_user_id')
        fellowship_type = data.get('fellowship_type')
        reciprocal_fellowship_type = RECIPROCAL_FELLOWSHIP_MAP.get(fellowship_type)

        if from_user == to_user:
            raise serializers.ValidationError({"error": "You cannot send a fellowship request to yourself."})

        existing_fellowship = Fellowship.objects.filter(
            Q(from_user=from_user, to_user=to_user, fellowship_type=fellowship_type, status='Accepted') |
            Q(from_user=to_user, to_user=from_user, fellowship_type=reciprocal_fellowship_type, status='Accepted')
        ).exists()
        if existing_fellowship:
            raise serializers.ValidationError({
                "error": f"A fellowship of type '{fellowship_type}' or its reciprocal already exists."
            })

        existing_reciprocal_fellowship = Fellowship.objects.filter(
            Q(from_user=from_user, to_user=to_user, fellowship_type=reciprocal_fellowship_type, status='Accepted') |
            Q(from_user=to_user, to_user=from_user, fellowship_type=fellowship_type, status='Accepted')
        ).exists()
        if existing_reciprocal_fellowship:
            raise serializers.ValidationError({
                "error": f"A reciprocal fellowship of type '{reciprocal_fellowship_type}' already exists."
            })
            
        duplicate_fellowship = Fellowship.objects.filter(
            from_user=from_user,
            to_user=to_user,
            fellowship_type=fellowship_type,
            status='Pending'
        ).exists()
        if duplicate_fellowship:
            raise serializers.ValidationError({
                "error": f"A pending fellowship request as '{fellowship_type}' already exists."
            })

        reciprocal_pending_fellowship = Fellowship.objects.filter(
            Q(from_user=from_user, to_user=to_user, status='Pending') |
            Q(from_user=to_user, to_user=from_user, status='Pending'),
            fellowship_type=reciprocal_fellowship_type
        ).exists()
        if reciprocal_pending_fellowship:
            raise serializers.ValidationError({
                "error": f"You cannot send a fellowship request as '{fellowship_type}' because a pending request already exists as '{reciprocal_fellowship_type}'."
            })
        return data

    def create(self, validated_data):
        to_user = validated_data.pop('to_user_id')
        reciprocal_fellowship_type = validated_data.pop('reciprocal_fellowship_type', None)
        return Fellowship.objects.create(
            to_user=to_user,
            reciprocal_fellowship_type=reciprocal_fellowship_type,
            **validated_data
        )


# ACADEMIC RECORD Serializer --------------------------------------------------------------------------------
class AcademicRecordSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = AcademicRecord
        fields = '__all__'


# MIGRATION HISTORY Serializer -----------------------------------------------------------------------------------
class MigrationHistorySerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)  # نمایش نام کاربری به جای ID کاربر

    class Meta:
        model = MigrationHistory
        fields = ['user', 'migration_type', 'migration_date']


# MEMBER SERVICE Serializer -----------------------------------------------------------------------------------
class MemberServiceTypeSerializer(serializers.ModelSerializer):
    service = SpiritualServiceSerializer(read_only=True)

    class Meta:
        model = MemberServiceType
        fields = ['id', 'service', 'history', 'document', 'register_date', 'is_approved', 'is_active']
        read_only_fields = ['id', 'is_active', 'is_approved', 'register_date']

    def validate_history(self, value):
        """Custom validation for history field."""
        if len(value) > 500:
            raise serializers.ValidationError("History cannot be longer than 500 characters.")
        return value

    def create(self, validated_data):
        """Override create method if needed to add additional logic."""
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Override update method if needed."""
        instance.service = validated_data.get('service', instance.service)
        instance.history = validated_data.get('history', instance.history)
        instance.document = validated_data.get('document', instance.document)
        instance.is_approved = validated_data.get('is_approved', instance.is_approved)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()
        return instance


# MEMBER Serializer ------------------------------------------------------------------------------
class MemberSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(context=None)
    service_types = MemberServiceTypeSerializer(many=True, read_only=True)
    organization_memberships = OrganizationSerializer(many=True, read_only=True)
    academic_record = AcademicRecordSerializer()
    
    class Meta:
        model = Member
        fields = [
            'user', 'service_types', 'organization_memberships', 'academic_record', 'testimony',
            'spiritual_rebirth_day', 'biography', 'vision', 'denominations_type',
            'show_gifts_in_profile', 'show_fellowship_in_profile', 'is_hidden_by_confidants',
            'register_date', 'identity_verification_status', 'is_verified_identity', 'identity_verified_at', 'is_sanctuary_participant',
            'is_privacy', 'is_migrated', 'is_active'
        ]
        read_only_fields = ['register_date', 'is_migrated', 'is_active', 'identity_verification_status', 'identity_verified_at', 'is_verified_identity', 'is_sanctuary_participant']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        context = kwargs.pop("context", {})
        if 'context' in kwargs:
            self.fields["user"] = CustomUserSerializer(context=context)

    def update(self, instance, validated_data):
        print('-------------------------   111')
        custom_user_data = validated_data.pop('user', None)
        if custom_user_data:
            custom_user_serializer = CustomUserSerializer(instance.user, data=custom_user_data, partial=True)
            if custom_user_serializer.is_valid():
                custom_user_serializer.save()
            else:
                raise serializers.ValidationError({"error": "Custom user update failed. Please check the provided data."})
            
        # Handle AcademicRecord data
        academic_record_data = validated_data.pop('academic_record', None)
        if academic_record_data:
            academic_record_instance = instance.academic_record
            if not academic_record_instance:
                academic_record_instance = AcademicRecord.objects.create()
                instance.academic_record = academic_record_instance
                instance.save()

            academic_record_serializer = AcademicRecordSerializer(
                academic_record_instance, data=academic_record_data, partial=True
            )
            if academic_record_serializer.is_valid():
                academic_record_serializer.save()
            else:
                raise serializers.ValidationError({"error": "Academic record update failed. Please check the provided data."})
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
       
    def validate_biography(self, value):
        #  Ensure biography does not exceed 300 characters
        if len(value) > 300:
            raise serializers.ValidationError({"error": "Biography cannot exceed 300 characters."})
        return value

    def validate_spiritual_rebirth_day(self, value):
        # Validation for spiritual_rebirth_day to ensure it is not in the future
        if value > timezone.now().date():
            raise serializers.ValidationError({"error": "Spiritual rebirth day cannot be in the future."})
        return value


# MEMBER Serializer ------------------------------------------------------------------------------
class PublicMemberSerializer(serializers.ModelSerializer):
    user = PublicCustomUserSerializer(read_only=True)

    class Meta:
        model = Member
        fields = [
            'user', 'biography', 'vision', 'service_types', 'denominations_type',
        ]
        read_only_fields = fields
        
    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', None)
        super().__init__(*args, **kwargs)
        if context:
            self.fields['user'] = PublicCustomUserSerializer(context=context)


# LIMITED MEMBER Serializer ------------------------------------------------------------------------------
class LimitedMemberSerializer(serializers.ModelSerializer):
    user = LimitedCustomUserSerializer(read_only=True)

    class Meta:
        model = Member
        fields = [
            'user', 'biography', 'spiritual_rebirth_day',
            'register_date',
        ]
        read_only_fields = ['user', 'register_date']
        
    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', None)
        super().__init__(*args, **kwargs)
        if context:
            self.fields['user'] = LimitedCustomUserSerializer(context=context)



    
    
# MEMBER'S GIFT serializer -----------------------------------------------------------------------------
# Spritual Gifts
class SpiritualGiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpiritualGift
        fields = ['id', 'name', 'description']
        

# Gift Question serializer
class SpiritualGiftSurveyQuestionSerializer(serializers.ModelSerializer):
    gift = SpiritualGiftSerializer()

    class Meta:
        model = SpiritualGiftSurveyQuestion
        fields = ['id', 'question_text', 'question_number', 'language', 'options', 'gift']
        
# Gift Survey serializer
class SpiritualGiftSurveyResponseSerializer(serializers.ModelSerializer):
    question = SpiritualGiftSurveyQuestionSerializer()

    class Meta:
        model = SpiritualGiftSurveyResponse
        fields = ['id', 'member', 'question', 'answer']
        
    def validate_answer(self, value):
        if value < 1 or value > 7:
            raise serializers.ValidationError("Answer must be between 1 and 7.")
        return value

    def validate(self, data):
        question = data.get('question')
        member = data.get('member')
        if not SpiritualGiftSurveyQuestion.objects.filter(id=question.id).exists():
            raise serializers.ValidationError("The question is not valid.")
        if not Member.objects.filter(user=member).exists():
            raise serializers.ValidationError("The member is not valid.")
        return data
        
# Member Gifts serializer
class MemberSpiritualGiftsSerializer(serializers.ModelSerializer):
    gifts = SpiritualGiftSerializer(many=True)
    survey_results = serializers.JSONField()

    class Meta:
        model = MemberSpiritualGifts
        fields = ['member', 'gifts', 'survey_results', 'created_at']
        
        
        
        




# GUESTUSER serializer ----------------------------------------------------------------------------------
class GuestUserSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)

    class Meta:
        model = GuestUser
        fields = ['user', 'register_date', 'is_migrated', 'is_active', 'slug']
        read_only_fields = ['user', 'register_date', 'is_migrated', 'is_active', 'slug']

    def update(self, instance, validated_data):
        # Update CustomUser fields
        custom_user_data = validated_data.pop('user', None)
        if custom_user_data:
            custom_user_serializer = CustomUserSerializer(instance.user, data=custom_user_data, partial=True)
            if custom_user_serializer.is_valid():
                custom_user_serializer.save()


# LIMITED GUESTUSER serializer -----------------------------------------------------------------
class LimitedGuestUserSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())

    class Meta:
        model = GuestUser
        fields = ['user', 'register_date', 'slug']
        read_only_fields = ['user', 'register_date', 'slug']

    
# CLIENT serializer ------------------------------------------------------------------ 
# Client Request 
class ClientRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientRequest
        fields = ['id', 'request', 'description', 'document_1', 'document_2', 'register_date', 'is_active']
        read_only_fields = ['register_date']

    def validate_document_1(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("The document size exceeds the limit of 2MB.")
        valid_file_types = ['application/pdf', 'image/jpeg', 'image/png']
        if value and value.content_type not in valid_file_types:
            raise serializers.ValidationError("Only PDF, JPEG, and PNG files are allowed.")
        return value

    def validate_document_2(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("The document size exceeds the limit of 2MB.")
        valid_file_types = ['application/pdf', 'image/jpeg', 'image/png']
        if value and value.content_type not in valid_file_types:
            raise serializers.ValidationError("Only PDF, JPEG, and PNG files are allowed.")
        return value

    def validate(self, data):
        if not data.get('document_1') and not data.get('document_2'):
            raise serializers.ValidationError("At least one document should be uploaded.")
        return data
           
# Client
class ClientSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())
    organization_clients = SimpleOrganizationSerializer(many=True, read_only=True)
    request = ClientRequestSerializer(read_only=True)

    class Meta:
        model = Client
        fields = ['user', 'organization_clients', 'request', 'register_date', 'is_active', 'slug']
        read_only_fields = ['register_date', 'slug']

    def validate(self, data):
        if data.get('is_active') and not data.get('request'):
            raise serializers.ValidationError("Active client must have a request.")
        return data
    
    
# CUSTOMER serializer ------------------------------------------------------------------ 
class CustomerSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())
    billing_address = AddressSerializer(read_only=True)
    shipping_addresses = AddressSerializer(many=True, read_only=True)
    customer_phone_number = serializers.CharField(
        max_length=20, 
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")]
    )
    
    class Meta:
        model = Customer
        fields = ['user', 'billing_address', 'shipping_addresses', 'customer_phone_number', 'register_date', 'deactivation_reason', 'deactivation_note', 'is_active']
        read_only_fields = ['user', 'register_date', 'is_active']

    def validate_shipping_addresses(self, value):
        if not value:
            raise serializers.ValidationError("Shipping addresses cannot be empty.")
        return value