from rest_framework import serializers
from .models import Organization, Branch, Review, Video, Playlist

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'

class BranchSerializer(serializers.ModelSerializer):

    google_review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)    
    yandex_review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)    
    twogis_review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)    
    vlru_review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)    

    class Meta:
        model = Branch
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):

    rating = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)

    class Meta:
        model = Review
        fields = '__all__'


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = '__all__'


class PlaylistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = '__all__'