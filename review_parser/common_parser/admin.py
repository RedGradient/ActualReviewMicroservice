from django.contrib import admin, messages
from django.shortcuts import redirect

from .models import Branch, BranchPlatform, Organization, Review


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "address", "created_at")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
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
    change_list_template = "admin/common_parser/review/change_list.html"
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

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST" and "_delete_all" in request.POST:
            count = Review.objects.count()
            Review.objects.all().delete()
            self.message_user(request, f"Удалено записей: {count}.", level=messages.SUCCESS)
            return redirect("admin:common_parser_review_changelist")

        return super().changelist_view(request, extra_context)
