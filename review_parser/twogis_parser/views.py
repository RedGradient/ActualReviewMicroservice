from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from twogis_parser.tools.parser import create_2gis_reviews
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


def parse_2gis(request):
    """Апи для загрузки отзывов с 2gis"""
    data = request.data
    inn = data.get('inn')
    org_name = data.get('org_name')
    address = data.get('address')
    url = data.get('url')
    count = data.get('count')   

    cnt = create_2gis_reviews(
                inn=inn,
                org_name=org_name,
                address=address,
                url=url,
                count=count
            )

    return Response({
            'message': f'Отзывов создано: {cnt}'
        }, status=status.HTTP_201_CREATED)
