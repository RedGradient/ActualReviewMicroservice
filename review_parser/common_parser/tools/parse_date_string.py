from datetime import datetime
import re

RU_MONTH_NAMES_TO_NUM = {
    'январь': '01', 'января': '01',
    'февраль': '02', 'февраля': '02',
    'март': '03', 'марта': '03',
    'апрель': '04', 'апреля': '04',
    'май': '05', 'мая': '05',
    'июнь': '06', 'июня': '06',
    'июль': '07', 'июля': '07',
    'август': '08', 'августа': '08',
    'сентябрь': '09', 'сентября': '09',
    'октябрь': '10', 'октября': '10',
    'ноябрь': '11', 'ноября': '11',
    'декабрь': '12', 'декабря': '12'
}

def replace_month_with_number(date_str):
    """Заменяет месяц на его цифровое представление"""
    pattern = r'\b(' + '|'.join(RU_MONTH_NAMES_TO_NUM.keys()) + r')\b'
    def replacer(match):
        return RU_MONTH_NAMES_TO_NUM[match.group()]
    return re.sub(pattern, replacer, date_str)

def parse_date_string(date_str):
    """ Парсит строку формата "DD MMMM YYYY" или "DD MMMM", возвращая объект datetime. Если год отсутствует, подставляет текущий год. """
    processed_date = replace_month_with_number(date_str).strip()
    parts = processed_date.split()
    
    if len(parts) < 3: 
        current_year = datetime.now().year
        processed_date += f" {current_year}"
        
    try:
        dt_obj = datetime.strptime(processed_date, "%d %m %Y")
        return dt_obj
    except ValueError as e:
        print(f"Произошла ошибка при парсинге даты: {e}")
        return None