from rest_framework import status
from rest_framework.response import Response

from common_parser.parsers.vlru.parser import create_vlru_reviews


def parse_vlru(request):
    """Апи для загрузки отзывов с vl.ru"""
    data = request.data
    inn = data.get("inn")
    org_name = data.get("org_name")
    address = data.get("address")
    url = data.get("url")

    cnt = create_vlru_reviews(inn=inn, org_name=org_name, address=address, url=url)

    return Response({"message": f"Отзывов создано: {cnt}"}, status=status.HTTP_201_CREATED)
