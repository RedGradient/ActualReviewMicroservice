from django.db import models
from django.utils import timezone
from django.utils.timezone import now


class Organization(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    inn = models.CharField(max_length=12, null=False, blank=False, unique=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.name or f"Организация #{self.id}"


class Branch(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="branches")
    address = models.TextField()

    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["organization", "address"],
                name="unique_organization_address",
            ),
        )

    def __str__(self):
        org = self.organization.name or f"ИНН {self.organization.inn}"
        address = self.address.strip()
        if len(address) > 60:
            address = f"{address[:57]}..."
        return f"#{self.pk} · {org} · {address}"


class BranchPlatform(models.Model):
    PROVIDER_CHOICES = (
        ("google", "Google"),
        ("yandex", "Yandex"),
        ("2gis", "2GIS"),
        ("vlru", "VL.ru"),
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="source",
        null=False,
        blank=False,
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        null=False,
        blank=False,
    )

    url = models.URLField(max_length=500, null=True, blank=True)

    org_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
    )

    review_count = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    review_avg = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        blank=True,
        null=True,
    )

    parsed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self) -> str:
        return f"{self.get_provider_display()} · {self.branch}"


class Review(models.Model):
    branch_platform = models.ForeignKey(BranchPlatform, on_delete=models.CASCADE, related_name="reviews")
    external_id = models.CharField(max_length=64, null=True, blank=True)
    author = models.CharField(max_length=255)
    avatar = models.URLField(null=True, blank=True)
    video = models.URLField(null=True, blank=True)
    photos = models.TextField(null=True, blank=True)
    published_date = models.DateTimeField(default=now)
    rating = models.CharField(null=True, blank=True)
    content = models.TextField()

    content_hash = models.CharField(max_length=64, db_index=True)

    review_url = models.URLField(max_length=250, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"{self.author}'s review for {self.branch_platform.branch}"


class BranchIPMapping(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="ip_mappings")
    ip_address = models.GenericIPAddressField()

    def __str__(self):
        return f"{self.ip_address} → Филиал {self.branch.id} : {self.branch.address}"


class Playlist(models.Model):
    PROVIDER_CHOICES = (
        ("youtube", "Ютуб"),
        ("vk", "Вк"),
    )

    title = models.CharField(max_length=255, blank=True, null=True)
    count = models.PositiveIntegerField(blank=True, null=True, default=None)
    url = models.URLField(unique=True)
    parse_date = models.DateTimeField(blank=True, null=True)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, null=True, blank=True)

    def __str__(self):
        return self.title or self.url


class Video(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="videos")
    url = models.URLField()
    title = models.CharField(max_length=255, blank=True, null=True)
    author = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateTimeField(blank=True, null=True)
    preview = models.URLField(max_length=1000, blank=True, null=True)
    duration = models.IntegerField(blank=True, null=True, default=None)

    def __str__(self):
        return self.title or self.url


class PlaylistIPMapping(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="ip_mappings_playlist")
    ip_address = models.GenericIPAddressField()

    def __str__(self):
        return f"{self.ip_address} → Playlist {self.playlist.id} : {self.playlist.title}"
