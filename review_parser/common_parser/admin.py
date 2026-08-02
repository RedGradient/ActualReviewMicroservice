from django.contrib import admin

from .models import Branch, BranchPlatform, Organization, Review

admin.site.register(Branch)
admin.site.register(BranchPlatform)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inn")
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
