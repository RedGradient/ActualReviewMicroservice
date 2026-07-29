from rest_framework import status
from rest_framework.response import Response

from common_parser.parsers.twogis.parser import create_2gis_reviews


def parse_2gis(request):
    """Апи для загрузки отзывов с 2gis"""
    data = request.data
    inn = data.get("inn")
    org_name = data.get("org_name")
    address = data.get("address")
    url = data.get("url")
    count = data.get("count")

    cnt = create_2gis_reviews(inn=inn, org_name=org_name, address=address, url=url, count=count)

    return Response({"message": f"Отзывов создано: {cnt}"}, status=status.HTTP_201_CREATED)
