from django.db import models
from django.utils.timezone import now
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.transaction import on_commit

class Organization(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    inn = models.CharField(max_length=12, null=False, blank=False, unique=True)
    
    def __str__(self):
        return self.name or f'Организация #{self.id}'


class Branch(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches"
    )
    address = models.TextField()
    google_map_url = models.URLField(max_length=1500, null=True, blank=True)
    yandex_map_url = models.URLField(max_length=1500, null=True, blank=True)
    twogis_map_url = models.URLField(max_length=500, null=True, blank=True)
    vlru_url = models.URLField(max_length=500, null=True, blank=True)
    vlru_org_id = models.CharField(max_length=16, null=True, blank=True) 
    google_review_count = models.IntegerField(null=True, blank=True)
    google_review_avg = models.FloatField(null=True, blank=True)
    google_parse_date = models.DateTimeField(blank=True, null=True)
    yandex_review_count = models.IntegerField(null=True, blank=True)
    yandex_review_avg = models.FloatField(null=True, blank=True)
    yandex_parse_date = models.DateTimeField(blank=True, null=True)
    twogis_review_count = models.IntegerField(null=True, blank=True)
    twogis_review_avg = models.FloatField(null=True, blank=True)
    twogis_parse_date = models.DateTimeField(blank=True, null=True)
    vlru_parse_date = models.DateTimeField(blank=True, null=True)
    vlru_review_count = models.IntegerField(null=True, blank=True)
    vlru_review_avg = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'address'],
                name='unique_organization_address'
            )
        ]

    def __str__(self):
        return f'{self.id} : {self.organization}: {self.address[:50]}'

@receiver(post_save, sender=Branch)
def send_notification(sender, instance, created, **kwargs):
    if created:
        from common_parser.tasks import parse_all_providers_async_on_create
        on_commit(lambda: parse_all_providers_async_on_create.delay(instance.organization.id, instance.address))


class Review(models.Model):

    PROVIDER_CHOICES = [
        ('yandex', 'Яндекс'),
        ('google', 'Гугл'),
        ('2gis', '2GIS'),
        ('vlru', 'VL.RU')
    ]

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="reviews")
    author = models.CharField(max_length=255)
    avatar = models.URLField(null=True, blank=True)
    video = models.URLField(null=True, blank=True)
    photos = models.TextField(null=True, blank=True)
    published_date = models.DateTimeField(default=now)
    rating = models.PositiveSmallIntegerField()
    content = models.TextField()

    review_url = models.URLField(max_length=250, null=True, blank=True)
    
    provider = models.CharField(
        max_length=10,
        choices=PROVIDER_CHOICES,
        null=True, blank=True
    )

    def __str__(self):
        return f"{self.author}'s review for {self.branch}"
    


class BranchIPMapping(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='ip_mappings'
    )
    ip_address = models.GenericIPAddressField()
    
    def __str__(self):
        return f"{self.ip_address} → Филиал {self.branch.id} : {self.branch.address}"
    



class Playlist(models.Model):

    PROVIDER_CHOICES = [
        ('youtube', 'Ютуб'),
        ('vk', 'Вк'),
    ]

    title = models.CharField(max_length=255, blank=True, null=True)
    count = models.PositiveIntegerField(blank=True, null=True, default=None)
    url = models.URLField(unique=True)
    parse_date = models.DateTimeField(blank=True, null=True)
    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        null=True, blank=True
    )
    
    def __str__(self):
        return self.title or self.url

@receiver(post_save, sender=Playlist)
def send_notification(sender, instance, created, **kwargs):
    if created:
        from common_parser.tasks import parse_youtube_videos_async, parse_vk_videos_async
        if "youtube" in instance.url:
            on_commit(lambda: parse_youtube_videos_async.delay(instance.id))
        elif "vk" in instance.url:
            on_commit(lambda: parse_vk_videos_async.delay(instance.id))

class Video(models.Model):
    url = models.URLField()
    title = models.CharField(max_length=255, blank=True, null=True)
    author = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateTimeField(blank=True, null=True)
    preview = models.URLField(max_length=1000, blank=True, null=True)
    duration = models.IntegerField(blank=True, null=True, default=None)
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='videos')
    
    def __str__(self):
        return self.title or self.url
    

class PlaylistIPMapping(models.Model):
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name='ip_mappings_playlist'
    )
    ip_address = models.GenericIPAddressField()
    
    def __str__(self):
        return f"{self.ip_address} → Playlist {self.playlist.id} : {self.playlist.title}"