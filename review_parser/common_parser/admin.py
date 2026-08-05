from django.contrib import admin

from .models import Branch, BranchPlatform, Organization, Review


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "address", "created_at")


@admin.register(Organization)
class Organization(admin.ModelAdmin):
    list_display = ("id", "name", "inn", "created_at")


@admin.register(BranchPlatform)
class BranchPlatformAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "branch",
        "provider",
        "url",
        "review_count",
        "review_avg",
        "parsed_at",
        "created_at",
    )
    list_filter = ("provider",)
    ordering = ("id",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "rating",
        "published_date",
        "external_id",
        "review_url",
        "created_at",
        "branch_platform",
    )
    ordering = ("-published_date",)
    search_fields = ("author", "content")
