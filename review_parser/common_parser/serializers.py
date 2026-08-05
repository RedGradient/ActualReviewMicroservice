from rest_framework import serializers

from .models import Branch, BranchPlatform, Organization, Playlist, Review, Video

VALID_PROVIDERS = [choice[0] for choice in BranchPlatform.PROVIDER_CHOICES]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("name", "inn")


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ("organization", "address")


class BranchPlatformSerializer(serializers.ModelSerializer):
    review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)

    class Meta:
        model = BranchPlatform
        fields = (
            "branch",
            "provider",
            "url",
            "org_id",
            "review_count",
            "review_avg",
            "parsed_at",
        )


class ReviewPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = (
            "external_id",
            "author",
            "rating",
            "content",
            "published_date",
            "review_url",
            "avatar",
            "video",
            "photos",
        )


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = (
            "branch_platform",
            "external_id",
            "author",
            "rating",
            "content",
            "content_hash",
            "published_date",
            "review_url",
            "avatar",
            "video",
            "photos",
        )


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = "__all__"


class PlaylistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = "__all__"


class GetReviewsSerializer(serializers.Serializer):
    branch_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=VALID_PROVIDERS)
    limit = serializers.IntegerField(default=50, min_value=1, max_value=500)
    offset = serializers.IntegerField(default=0, min_value=0)


class SyncReviewsSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    branch_id = serializers.IntegerField()
    providers = serializers.ListField(
        child=serializers.ChoiceField(choices=VALID_PROVIDERS),
        allow_empty=False,
    )


class TaskQuerySerializer(serializers.Serializer):
    task_id = serializers.CharField()
