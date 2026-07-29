from rest_framework import status
from rest_framework.response import Response

from common_parser.parsers.yandex.parser import create_yandex_reviews


def parse_yandex(request):
    data = request.data
    inn = data.get("inn")
    org_name = data.get("org_name")
    address = data.get("address")
    url = data.get("url")
    count = data.get("count")

    cnt = create_yandex_reviews(inn=inn, org_name=org_name, address=address, url=url, count=count)

    return Response({"message": f"Отзывов создано: {cnt}"}, status=status.HTTP_201_CREATED)
