# # apps/profiles/helpers/testimonies.py

# from django.contrib.contenttypes.models import ContentType

# from apps.profiles.models.member import Member
# from apps.posts.models.testimony import Testimony


# VISIBLE_FILTERS = dict(
#     is_active=True,
#     is_hidden=False,
#     is_restricted=False,
#     is_suspended=False,
# )


# def testimonies_for_member(member: Member):
#     """
#     Return latest testimony per type for a member.
#     """
#     ct = ContentType.objects.get_for_model(member.__class__)
#     base_qs = Testimony.objects.filter(
#         content_type=ct,
#         object_id=member.id,
#         **VISIBLE_FILTERS,
#     )

#     by_type = {"audio": None, "video": None, "written": None}

#     for t in (Testimony.TYPE_AUDIO, Testimony.TYPE_VIDEO, Testimony.TYPE_WRITTEN):
#         inst = (
#             base_qs.filter(type=t)
#             .order_by("-published_at", "-updated_at", "-id")
#             .first()
#         )
#         by_type[t] = inst

#     return by_type