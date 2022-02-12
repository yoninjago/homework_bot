import logging
import os
import sys
import time

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

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

MESSAGE = 'Бот отправил сообщение: {message}'
RESPONSE_ERROR = ('Эндпоинт {endpoint} недоступен.'
                  'Код ответа API: {status_code}')
UNEXPECTED_RESPONSE = 'Неожиданный ответ сервера: {error}'
RESPONSE_MISSING_KEYS = ('Домашняя работа не содержит необходимые поля.'
                         'Имя работы: {homework_name}'
                         'Статус: {homework_status}')
UNEXPECTED_RESPONSE_TYPE = 'Неожиданный формат данных ответа: {type}'
UNEXPECTED_HOMEWORK_TYPE = ('Неожиданный формат данных '
                            'домашнего задания: {type}')
UNEXPECTED_STATUS = 'Неожиданный статус домашней работы: {status}'
HOMEWORK_STATUS_CHANGE = ('Изменился статус проверки работы "{homework_name}".'
                          ' {verdict}')
ENVIRONMENT_VARIABLES_MISSING = ('Отсутствуют переменные окружения. '
                                 'Работа программы прекращена')
STATUS_NOT_CHANGE = 'В ответе отсутствуют новые статусы домашней работы'
ERROR_MESSAGE = 'Сбой в работе программы: {error}'


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] Event: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщений в Telegram чат."""
    logger.info(MESSAGE.format(message=message))
    return bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if not homework_statuses.status_code // 100 == 2:
            raise ValueError(RESPONSE_ERROR.format(
                endpoint=ENDPOINT, status_code=homework_statuses.status_code
            ))
    except requests.exceptions.RequestException as error:
        raise ValueError(UNEXPECTED_RESPONSE.format(error=error))
    return homework_statuses.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if type(response) != dict:
        raise TypeError(UNEXPECTED_RESPONSE_TYPE.format(type=type(response)))
    if type(response.get('homeworks')) != list:
        raise TypeError(UNEXPECTED_HOMEWORK_TYPE.format(
            type=type(response.get('homeworks'))
        ))
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None or homework_status is None:
        raise KeyError(RESPONSE_MISSING_KEYS.format(
            homework_name=homework_name, homework_status=homework_status
        ))
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if not verdict:
        raise KeyError(UNEXPECTED_STATUS.format(status=homework_status))
    return HOMEWORK_STATUS_CHANGE.format(
        homework_name=homework_name, verdict=verdict
    )


def check_tokens():
    """Проверяет доступность необходимых переменных окружения."""
    for token in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if not token:
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return logger.critical(ENVIRONMENT_VARIABLES_MISSING)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    homework = []
    count_error = 0
    while True:
        try:
            response = get_api_answer(current_timestamp)
            new_homework = check_response(response)
            if new_homework != homework and new_homework:
                send_message(bot, parse_status(new_homework[0]))
                homework = new_homework
            else:
                logger.debug(STATUS_NOT_CHANGE)
        except Exception as error:
            logger.error(error)
            if count_error == 0:
                send_message(bot, ERROR_MESSAGE.format(error=error))
                count_error += 1
            time.sleep(RETRY_TIME)
        else:
            count_error = 0
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
