from rest_framework import serializers
from .models import (
    Brand, ProductGroup, Feature, Product, FeatureValue, ProductFeature, Gallery
)

# Brand Serializer --------------------------------------------
class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['id', 'brand_title', 'image_name', 'slug', 'url_name']


# Product Group Serializer --------------------------------------------
class ProductGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductGroup
        fields = [
            'id', 'group_title', 'image_name', 'description', 'group_parent',
            'register_date', 'published_date', 'update_date', 'is_active', 'slug', 'url_name'
        ]


# Feature Serializer --------------------------------------------
class FeatureSerializer(serializers.ModelSerializer):
    product_groups = ProductGroupSerializer(many=True, read_only=True)

    class Meta:
        model = Feature
        fields = ['id', 'feature', 'product_groups']


# Feature Value Serializer --------------------------------------------
class FeatureValueSerializer(serializers.ModelSerializer):
    feature = serializers.StringRelatedField()  # To display feature name instead of its ID

    class Meta:
        model = FeatureValue
        fields = ['id', 'value_title', 'feature']


# Product Feature Serializer --------------------------------------------
class ProductFeatureSerializer(serializers.ModelSerializer):
    feature = serializers.StringRelatedField()  # Display feature name instead of its ID
    feature_value = serializers.StringRelatedField()  # Display feature value name instead of its ID

    class Meta:
        model = ProductFeature
        fields = ['id', 'product', 'feature', 'feature_value']


# Product Serializer --------------------------------------------
class ProductSerializer(serializers.ModelSerializer):
    product_groups = ProductGroupSerializer(many=True, read_only=True)
    brand = BrandSerializer(read_only=True)
    features = ProductFeatureSerializer(source='product_features', many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'product_name', 'summary_description', 'description', 'image_name', 'product_groups',
            'brand', 'features', 'register_date', 'published_date', 'update_date',
            'selling_type', 'price', 'is_active', 'slug', 'url_name'
        ]


# Gallery Serializer --------------------------------------------
class GallerySerializer(serializers.ModelSerializer):
    product_gallery = serializers.StringRelatedField()  # Display product name instead of its ID

    class Meta:
        model = Gallery
        fields = ['id', 'product_gallery', 'image_name']



















# from rest_framework import serializers
# from .models import Product, ProductGroup

# class ProductSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Product
#         fields = '__all__'
        
# class ProductGroupSerializer(serializers.ModelSerializer):
#     products = serializers.SerializerMethodField()
#     class Meta:
#         model = ProductGroup
#         fields = '__all__'
    
#     def get_products(self, obj):
#         result = obj.products.all()
#         return ProductSerializer(instance=result, many=True)

 
# class ProductGroupsSerializer(serializers.ModelSerializer):
#     count = serializers.IntegerField()
#     class Meta:
#         model = ProductGroup
#         fields = [
#             'id',
#             'group_title',
#             'image_name',
#             'description',
#             'register_date',
#             'published_date',
#             'update_date',
#             'is_active',
#             'slug',
#             'group_parent',
#             'count', 
#         ]