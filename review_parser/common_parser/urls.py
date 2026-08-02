from django.urls import path
from rest_framework.routers import DefaultRouter

from common_parser.views import (
    BranchPlatformView,
    BranchView,
    OrganizationView,
    get_reviews,
    sync_reviews,
    tasks,
)

router = DefaultRouter()
router.register("organizations", OrganizationView, basename="organization")
router.register("branches", BranchView, basename="branch")
router.register("branch-platforms", BranchPlatformView, basename="branch-platform")

urlpatterns = [
    path("reviews/", get_reviews),
    path("sync/", sync_reviews),
    path("tasks/", tasks),
    *router.urls,
]
