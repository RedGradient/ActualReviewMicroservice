from django.contrib import admin, messages
from django.shortcuts import redirect

from common_parser.tasks import parse_single_provider

from .models import Branch, BranchPlatform, Organization, Review


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "address", "created_at")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inn", "created_at")


@admin.register(BranchPlatform)
class BranchPlatformAdmin(admin.ModelAdmin):
    change_form_template = "admin/common_parser/branchplatform/change_form.html"
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("branch", "branch__organization")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.method == "POST" and "_parse_provider" in request.POST:
            branch_platform = self.get_object(request, object_id)
            if branch_platform is None:
                return redirect("admin:common_parser_branchplatform_changelist")

            task = parse_single_provider.delay(
                branch_platform.provider,
                branch_platform.branch.organization_id,
                branch_platform.branch_id,
            )
            self.message_user(
                request,
                (
                    f"Парсинг {branch_platform.get_provider_display()} "
                    f"для филиала #{branch_platform.branch_id} запущен. task_id={task.id}"
                ),
                level=messages.SUCCESS,
            )
            return redirect("admin:common_parser_branchplatform_change", object_id)

        return super().change_view(request, object_id, form_url, extra_context)


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
