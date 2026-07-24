from common_parser.serializers import ReviewSerializer, OrganizationSerializer, BranchSerializer, VideoSerializer
from common_parser.models import Review, Organization, Branch, Video, Playlist

def create_review(data: dict)->bool:
    """Создает отзыв, если уже есть такой отзыв возвращает False"""
    existing_review = Review.objects.filter(
        branch=data["branch"],
        author=data["author"],
        content=data["content"]
    ).exists()

    if existing_review:
        return False
    
    data_rewiew={
                    'branch': data["branch"].id,
                    'author': data["author"],
                    'avatar': data["avatar"],
                    'rating': data["rating"],
                    'content': data["content"],
                    'published_date': data["published_date"],
                    'provider': data['provider']
                }
    
    if "photos" in data:
        data_rewiew["photos"] = data["photos"]

    if "video" in data:
        data_rewiew["video"] = data["video"]

    if "review_url" in data:
        data_rewiew["review_url"] = data["review_url"]

    serializer_review = ReviewSerializer(data = data_rewiew)
    
    if serializer_review.is_valid():
        serializer_review.save()
        return True
    else:
        print("Ошибки сериализатора:", serializer_review.errors)
        return False
    
def get_or_create_Organization(inn: str, name:str) -> Organization:
        try:
            organization = Organization.objects.get(inn=inn)
            if name and organization.name != name:
                organization.name = name 
                organization.save()
        except Organization.DoesNotExist:
            serializer_org = OrganizationSerializer(data={
            "inn": inn,
            "name": name or ""
            })
            if serializer_org.is_valid():
                organization = serializer_org.save()
            else:
                return None
        
        return organization

def get_or_create_Branch(organization: str, address: str, url_name: str, url: str, review_count_name: str, review_count: str, review_avg_name: str, review_avg: str) -> Branch:
    try:
        branch = Branch.objects.get(address=address, organization=organization)
        if url and getattr(branch, url_name) != url:
            setattr(branch,url_name,url)
        if review_count and getattr(branch, review_count_name) != review_count:
            setattr(branch, review_count_name, review_count)
        if review_avg and getattr(branch, review_avg_name) != review_avg:
            setattr(branch, review_avg_name, review_avg)
        branch.save()
    except Branch.DoesNotExist:
        serializer_branch = BranchSerializer(data={
            'organization': organization.id,
            'address': address or "",
            url_name: url
        })
        if serializer_branch.is_valid():
            branch = serializer_branch.save()
        else:
            return None
    
    return branch


def get_or_create_playlist(data: dict)->Playlist:
    playlist_url = data.get('url')
    
    try:
        playlist = Playlist.objects.get(url=playlist_url)

        for key, value in data.items():
            setattr(playlist, key, value)

        playlist.save()
        return playlist
    
    except Playlist.DoesNotExist:

        new_playlist = Playlist(**data)
        new_playlist.save()

        return new_playlist


def create_video(data: dict)-> bool:
    """Создает видео, если уже есть такое возвращает False"""
    existing_review = Video.objects.filter(
        url=data["url"]
    ).exists()

    if existing_review:
        return False

    serializer_video = VideoSerializer(data = data)
    
    if serializer_video.is_valid():
        serializer_video.save()
        return True
    else:
        print("Ошибки сериализатора:", serializer_video.errors)
        return False
