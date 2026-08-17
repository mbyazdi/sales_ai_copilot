# recommendations/serializers.py

from rest_framework import serializers


class RecommendationSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    product_code = serializers.CharField()
    product_name = serializers.CharField()
    category = serializers.CharField()
    score = serializers.DecimalField(
        max_digits=10,
        decimal_places=4
    )
    recommendation_type = serializers.CharField()
    reason = serializers.CharField()


class RecommendationResponseSerializer(serializers.Serializer):

    customer_code = serializers.CharField()

    count = serializers.IntegerField()

    engine_version = serializers.CharField()

    recommendations = RecommendationSerializer(
        many=True
    )