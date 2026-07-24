from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from vl_parser.tools.parser import create_vlru_reviews
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

def parse_vlru(request):
    """Апи для загрузки отзывов с vl.ru"""
    data = request.data
    inn = data.get('inn')
    org_name = data.get('org_name')
    address = data.get('address')
    url = data.get('url')
    count = data.get('count')   

    cnt = create_vlru_reviews(
                inn=inn,
                org_name=org_name,
                address=address,
                url=url,
                count=count
            )

    return Response({
            'message': f'Отзывов создано: {cnt}'
        }, status=status.HTTP_201_CREATED)
