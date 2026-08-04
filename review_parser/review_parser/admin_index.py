from django.contrib import admin, messages
from django.shortcuts import redirect

from common_parser.tasks import weekly_parsing

_original_index = admin.site.index


def custom_admin_index(request, extra_context=None):
    if request.method == "POST" and "_weekly_parsing" in request.POST:
        task = weekly_parsing.delay()
        messages.success(request, f"Weekly parsing запущен. task_id={task.id}")
        return redirect("admin:index")

    return _original_index(request, extra_context)


admin.site.index = custom_admin_index
admin.site.index_template = "admin/custom_index.html"
