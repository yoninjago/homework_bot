import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
LOG_FILENAME = __file__ + '.log'

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

MESSAGE = 'Отправка сообщения в чат: {message}'
RESPONSE_ERROR = ('Эндпоинт {endpoint} недоступен.'
                  'Код ответа API: {status_code}'
                  ' Используемые параметры запроса:'
                  ' url: {url}; headers: {headers}; params: {params}')
CONNECTION_ERROR = ('Проблемы с подключением к серверу: {error}.'
                    ' Используемые параметры запроса:'
                    ' url: {url}; headers: {headers}; params: {params}')
UNEXPECTED_RESPONSE = ('Неожиданный ответ сервера. Описание проблемы: {error}.'
                       ' Код ответа API: {status_code}.'
                       ' Используемые параметры запроса:'
                       ' url: {url}; headers: {headers}; params: {params}.')
UNEXPECTED_RESPONSE_TYPE = 'Неожиданный формат данных ответа: {type}'
UNEXPECTED_HOMEWORK_TYPE = ('Неожиданный формат данных '
                            'домашнего задания: {type}')
UNEXPECTED_STATUS = 'Неожиданный статус домашней работы: {status}'
HOMEWORK_STATUS_CHANGE = ('Изменился статус проверки работы "{homework_name}".'
                          ' {verdict}')
ENVIRONMENT_VARIABLES_MISSING = (
    'Отсутствует обязательная переменная окружения: {name}')
STOP_BOT = 'Программа принудительно остановлена.'
STATUS_NOT_CHANGE = 'В ответе отсутствуют новые статусы домашней работы'
ERROR_MESSAGE = 'Сбой в работе программы: {error}'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] Event: %(message)s')

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    LOG_FILENAME, maxBytes=1000000, backupCount=2
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def send_message(bot, message):
    """Отправка сообщений в Telegram чат."""
    logger.info(MESSAGE.format(message=message))
    return bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    REQUEST = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': current_timestamp}
    }
    try:
        homework_statuses_json = requests.get(**REQUEST)
    except requests.exceptions.ConnectionError as error:
        raise ConnectionError(CONNECTION_ERROR.format(**REQUEST, error=error))
    homework_statuses = homework_statuses_json.json()
    for field in ['error', 'code']:
        if field in homework_statuses:
            raise RuntimeError(UNEXPECTED_RESPONSE.format(
                **REQUEST,
                error=homework_statuses.get(field),
                status_code=homework_statuses_json.status_code
            ))
    if homework_statuses_json.status_code != 200:
        raise ValueError(RESPONSE_ERROR.format(
            endpoint=ENDPOINT, status_code=homework_statuses_json.status_code
        ))
    return homework_statuses


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(UNEXPECTED_RESPONSE_TYPE.format(type=type(response)))
    if not isinstance(response.get('homeworks'), list):
        raise TypeError(UNEXPECTED_HOMEWORK_TYPE.format(
            type=type(response.get('homeworks'))
        ))
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы работы."""
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(UNEXPECTED_STATUS.format(status=status))
    return HOMEWORK_STATUS_CHANGE.format(
        homework_name=homework_name, verdict=HOMEWORK_VERDICTS[status]
    )


def check_tokens():
    """Проверяет доступность необходимых переменных окружения."""
    for name in ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']:
        if not globals()[name]:
            logger.critical(ENVIRONMENT_VARIABLES_MISSING.format(name=name))
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError(STOP_BOT)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    sent_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            new_homeworks = check_response(response)
            if new_homeworks:
                send_message(bot, parse_status(new_homeworks[0]))
            else:
                logger.debug(STATUS_NOT_CHANGE)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logger.exception(message)
            if sent_message != message:
                sent_message = message
                try:
                    send_message(bot, message)
                except Exception as error:
                    logger.exception(ERROR_MESSAGE.format(error=error))
            time.sleep(RETRY_TIME)
        else:
            current_timestamp = response.get('current_date', current_timestamp)


if __name__ == '__main__':
    main()
