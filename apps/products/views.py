from rest_framework import viewsets, filters, status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from .models import Product, ProductGroup
from .serializers import ProductSerializer, ProductGroupSerializer


# PRODUCT Viewset -----------------------------------------------------------------------------------
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


# RIVER HARVEST Viewset ------------------------------------------------------------------------------
class RiverHarvestViewSet(viewsets.ReadOnlyModelViewSet): # Marketplace
    queryset = Product.objects.filter(is_active=True, warehouse_inventory__quantity__gt=0).distinct()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product_name', 'brand__brand_title', 'product_groups__group_title']
    ordering_fields = ['price', 'published_date']

    @action(detail=False, methods=['get'], url_path='free')
    def get_free_products(self, request):
        free_products = self.queryset.filter(selling_type='free')
        serializer = self.get_serializer(free_products, many=True)
        return Response({'free_products': serializer.data}, status=200)

    @action(detail=False, methods=['get'], url_path='cheapest')
    def get_cheapest_products(self, request):
        cheapest_products = self.queryset.order_by('price')
        serializer = self.get_serializer(cheapest_products, many=True)
        return Response({'cheapest_products': serializer.data}, status=200)

    @action(detail=False, methods=['get'], url_path='expensive')
    def get_expensive_products(self, request):
        expensive_products = self.queryset.order_by('-price')
        serializer = self.get_serializer(expensive_products, many=True)
        return Response({'expensive_products': serializer.data}, status=200)

    @action(detail=False, methods=['get'], url_path='newest')
    def get_newest_products(self, request):
        newest_products = self.queryset.order_by('-published_date')
        serializer = self.get_serializer(newest_products, many=True)
        return Response({'newest_products': serializer.data}, status=200)

    @action(detail=False, methods=['get'], url_path='oldest')
    def get_oldest_products(self, request):
        oldest_products = self.queryset.order_by('published_date')
        serializer = self.get_serializer(oldest_products, many=True)
        return Response({'oldest_products': serializer.data}, status=200)


# COMPARE PRODUCT Viewset ---------------------------------------------------------------------------
class CompareProductView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        compare_product = request.session.get('compare_product', [])
        products = Product.objects.filter(id__in=compare_product, is_active=True)
        serializer = ProductSerializer(products, many=True)
        return Response({'compare_products': serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        product_id = request.data.get('product_id')
        if product_id:
            compare_product = request.session.get('compare_product', [])
            if product_id not in compare_product:
                compare_product.append(product_id)
                request.session['compare_product'] = compare_product
                request.session.modified = True
            return Response({'message': 'Product added to compare list.'}, status=status.HTTP_200_OK)
        return Response({'error': 'Product ID not provided.'}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        product_id = request.data.get('product_id')
        compare_product = request.session.get('compare_product', [])
        if product_id in compare_product:
            compare_product.remove(product_id)
            request.session['compare_product'] = compare_product
            request.session.modified = True
            return Response({'message': 'Product removed from compare list.'}, status=status.HTTP_200_OK)
        return Response({'error': 'Product not found in compare list.'}, status=status.HTTP_400_BAD_REQUEST)


# PRODUCT GROUP Viewset ----------------------------------------------------------------------------
class ProductGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductGroup.objects.filter(is_active=True).annotate(count=Count('products')).order_by('-count')
    serializer_class = ProductGroupSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['get'], url_path='products')
    def get_products_by_group(self, request, pk=None):
        product_group = get_object_or_404(ProductGroup, pk=pk, is_active=True)
        products = Product.objects.filter(Q(is_active=True) & Q(product_groups=product_group))
        serializer = ProductSerializer(products, many=True)
        return Response({'products_of_group': serializer.data}, status=status.HTTP_200_OK)
