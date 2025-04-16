from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Store
from .serializers import StoreSerializer



# STORE(ORG) ViewSet -----------------------------------------------------------------------------------
class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return Store.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        store = self.get_object()
        serializer = self.get_serializer(store)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        store = self.get_object()
        member = request.user.member
        if member not in store.organization.org_owners.all():
            return Response({"error": "Only organization owners can update the store."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        store = self.get_object()
        member = request.user.member
        if member not in store.organization.org_owners.all():
            return Response({"error": "Only organization owners can delete the store."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)
