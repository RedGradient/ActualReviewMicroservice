from rest_framework import serializers

from .models import Branch, BranchPlatform, Organization, Playlist, Review, Video


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = "__all__"


class BranchPlatformSerializer(serializers.ModelSerializer):
    review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)

    class Meta:
        model = BranchPlatform
        fields = "__all__"


class ReviewSerializer(serializers.ModelSerializer):
    rating = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)
    provider = serializers.CharField(source="branch_platform.provider", read_only=True)
    branch = serializers.IntegerField(source="branch_platform.branch_id", read_only=True)

    class Meta:
        model = Review
        fields = "__all__"


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = "__all__"


class PlaylistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = "__all__"
