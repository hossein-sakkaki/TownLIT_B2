# helpers.py یا کنار Serializer (هرجا منسجم‌تر است)
from django.contrib.contenttypes.models import ContentType
from apps.posts.models import Testimony

VISIBLE_FILTERS = dict(is_active=True, is_hidden=False, is_restricted=False, is_suspended=False)

def testimonies_for_member(member):
    """
    {
      'audio':   Testimony|None,
      'video':   Testimony|None,
      'written': Testimony|None,
    }
    """
    ct = ContentType.objects.get_for_model(member.__class__)  # امن‌تر از type(member)
    base_qs = (Testimony.objects
               .filter(content_type=ct, object_id=member.id, **VISIBLE_FILTERS))

    by_type = {'audio': None, 'video': None, 'written': None}
    # به‌صورت پیش‌فرض یکی از هر نوع داریم (Constraint شما)، پس first() کافیست.
    for t in (Testimony.TYPE_AUDIO, Testimony.TYPE_VIDEO, Testimony.TYPE_WRITTEN):
        inst = base_qs.filter(type=t).order_by('-published_at', '-updated_at', '-id').first()
        by_type[t] = inst
    return by_type
