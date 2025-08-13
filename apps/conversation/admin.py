from django.contrib import admin
from .models import Dialogue, DialogueParticipant, Message, UserDialogueMarker, MessageEncryption



# Inline for managing group participants
class DialogueParticipantInline(admin.TabularInline):
    model = DialogueParticipant
    extra = 1 
    fields = ('user', 'role')
    verbose_name = "Participant"
    verbose_name_plural = "Participants"




# Dialogue Admin -------------------------------------------------------------------------
@admin.register(Dialogue)
class DialogueAdmin(admin.ModelAdmin):
    list_display = ('group_name', 'is_group', 'created_at', 'display_participants', 'last_message_display', 'group_image')
    list_filter = ('is_group', 'created_at')
    search_fields = ('group_name', 'participants__username')
    filter_horizontal = ('participants', 'deleted_by_users')
    inlines = [DialogueParticipantInline]

    def display_participants(self, obj):
        """ Display list of chat participants """
        return ", ".join([user.username for user in obj.participants.all()])
    display_participants.short_description = 'Participants'

    def last_message_display(self, obj):
        """ Show the last message content if available """
        return obj.last_message.content_encrypted.decode() if obj.last_message and obj.last_message.content_encrypted else "No messages"
    last_message_display.short_description = "Last Message"


# Message Admin -------------------------------------------------------------------------
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('dialogue', 'sender', 'timestamp', 'get_seen_by', 'get_is_encrypted', 'display_deleted_by_users')
    list_filter = ('timestamp',)
    search_fields = ('sender__username', 'dialogue__group_name')
    readonly_fields = ('timestamp', 'content_encrypted', 'self_destruct_at')

    def get_seen_by(self, obj):
        return ", ".join([user.username for user in obj.seen_by_users.all()])
    get_seen_by.short_description = "Seen By"

    def get_is_encrypted(self, obj):
        return obj.is_encrypted
    get_is_encrypted.boolean = True
    get_is_encrypted.short_description = "Encrypted"

    def display_deleted_by_users(self, obj):
        return ", ".join([user.username for user in obj.deleted_by_users.all()])
    display_deleted_by_users.short_description = 'Deleted By'





# DialogueParticipant Admin -------------------------------------------------------------------------
@admin.register(DialogueParticipant)
class DialogueParticipantAdmin(admin.ModelAdmin):
    list_display = ('dialogue', 'user', 'role', 'get_role_display')
    list_filter = ('role',)
    search_fields = ('dialogue__group_name', 'user__username')


# UserDialogueMarker Admin -------------------------------------------------------------------------
@admin.register(UserDialogueMarker)
class UserDialogueMarkerAdmin(admin.ModelAdmin):
    list_display = ('user', 'dialogue', 'is_sensitive', 'delete_policy')
    list_filter = ('is_sensitive', 'delete_policy')
    search_fields = ('user__username', 'dialogue__group_name')




@admin.register(MessageEncryption)
class MessageEncryptionAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "device_id","created_at")
    # list_filter = ("device_id")
    search_fields = ("device_id", "message__id")
