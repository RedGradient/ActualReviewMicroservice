from rest_framework import serializers

from .models import Branch, BranchPlatform, Organization, Playlist, Review, Video

VALID_PROVIDERS = [choice[0] for choice in BranchPlatform.PROVIDER_CHOICES]


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
