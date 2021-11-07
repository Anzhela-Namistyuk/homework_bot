from http import HTTPStatus
import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

SECRET_PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
SECRET_TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
SECRET_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 300
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {SECRET_PRACTICUM_TOKEN}'}

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


class UnreachableEndpointException(Exception):
    """Исключение при недоступном Эндпоинте."""
    pass


def send_message(bot, message):
    """Отправляет сообщение в телеграмм_бот."""
    try:
        bot.send_message(SECRET_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}.',
                     exc_info=True)
    logger.info(f'Удачно отправленное сообщение: "{message}".')


def get_api_answer(url, current_timestamp):
    """Отправляет запрос к API домашки на эндпоинт."""
    payload = {'from_date': current_timestamp}
    try:
        response = requests.get(url, headers=HEADERS,
                                params=payload
                                )
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}.',
                     exc_info=True)
        raise error
    if response.status_code == HTTPStatus.OK:
        response = response.json()
        return response

    logger.error(f'Сбой в работе программы: Эндпоинт {ENDPOINT} '
                 f'недоступен. Код ответа API: {response.status_code}.')
    raise UnreachableEndpointException('Недоступен Эндпоинт.')


def parse_status(homework):
    """Анализирует статус проверки."""
    if homework['status'] in VERDICTS:
        verdict = VERDICTS[homework['status']]
        homework_name = homework.get('homework_name', 'latest homework')
        return ('Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    else:
        logger.error('Недокументированный статус '
                     f'проверки работы {homework.get("status")}.')
        return ('Недокументированный статус проверки'
                f' работы {homework.get("status")}.')


def check_response(response):
    """Проверяет полученный ответ.

    на корректность
    не изменился ли статус
    """
    homeworks = response.get('homeworks')
    if homeworks is None:
        logger.error('Ключ "homeworks" не существует.'
                     f' Все ключи {response.keys()}.')
        raise KeyError('Ключ "homeworks" не существует. '
                       f'Все ключи {response.keys()}.')
    if isinstance(homeworks, list) and len(homeworks) == 0:
        return homeworks
    if homeworks[0]['status'] not in VERDICTS:
        logger.error('Недокументированный статус домашней работы в ответе '
                     f'от API: {homeworks[0]["status"]}.')
        raise ValueError
    if isinstance(homeworks, list) and len(homeworks) > 0:
        return parse_status(homeworks[0])
    logger.error(f'Неверный тип значения по ключу homeworks {homeworks}.')
    raise TypeError('Неверный тип значения по ключу homeworks.')


def main():
    """Запускаем выполнение кода для телеграмм_бота."""
    for critical_env in [SECRET_TELEGRAM_TOKEN,
                         SECRET_PRACTICUM_TOKEN, SECRET_CHAT_ID]:
        if critical_env is None:
            logger.critical('Отсутствует обязательная переменная '
                            f'окружения: {critical_env}.')
    try:
        bot = telegram.Bot(token=SECRET_TELEGRAM_TOKEN)
    except Exception as error:
        logger.error(f'Ошибка при создании бота {error}')
    current_timestamp = int(time.time())
    status = 'Проект пока не проверяется.'
    while True:
        try:
            response = get_api_answer(ENDPOINT, current_timestamp)
            new_status = check_response(response)
            if new_status != status:
                send_message(bot, new_status)
                status = new_status
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error, exc_info=True)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
