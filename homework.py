import sys
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


class EmptyAnswerException(Exception):
    """Исключение если пришел пустом ответе с Эндпоинта."""

    pass


def send_message(bot, message):
    """Отправляет сообщение в телеграмм_бот."""
    try:
        bot.send_message(SECRET_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}.',
                     exc_info=True)
        sys.exit()
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
        return response.json()
    description_error = (f'Сбой в работе программы: Эндпоинт {ENDPOINT} '
                         f'недоступен. Код ответа API: {response.status_code}.')
    logger.error(description_error)
    raise UnreachableEndpointException(description_error)


def parse_status(homework):
    """Анализирует статус проверки."""
    if homework['status'] in VERDICTS:
        verdict = VERDICTS[homework['status']]
        homework_name = homework.get('homework_name', 'latest homework')
        return ('Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')


def check_response(response):
    """Проверяет полученный ответ.

    на корректность
    не изменился ли статус
    """

    if not response:
        description_error = f'Пришел пустой ответ с Эндпоинта: {ENDPOINT}'
        logger.error(description_error)
        raise EmptyAnswerException(description_error)

    homeworks = response.get('homeworks')

    if homeworks is None:
        description_error = ('Ключ "homeworks" не существует.'
                             f' Все ключи {response.keys()}.')
        logger.error(description_error)
        raise KeyError(description_error)

    if isinstance(homeworks, list) and len(homeworks) == 0:
        return homeworks

    if homeworks[0].get("status") not in VERDICTS:
        description_error = ('Недокументированный статус домашней работы в '
                             f'ответе от API: {homeworks[0].get("status")}.')
        logger.error(description_error)
        raise ValueError(description_error)

    if isinstance(homeworks, list) and len(homeworks) > 0:
        return parse_status(homeworks[0])

    description_error = ('Неверный тип значения по '
                         f'ключу homeworks {homeworks}.')
    logger.error(description_error)
    raise TypeError(description_error)


def main():
    """Запускаем выполнение кода для телеграмм_бота."""
    for critical_env in [SECRET_TELEGRAM_TOKEN,
                         SECRET_PRACTICUM_TOKEN, SECRET_CHAT_ID]:
        if critical_env is None:
            logger.critical('Отсутствует обязательная переменная '
                            f'окружения: {critical_env}.')
            sys.exit()
    try:
        bot = telegram.Bot(token=SECRET_TELEGRAM_TOKEN)
        send_message(bot, 'Приложение запущено')
    except Exception as error:
        logger.error(f'Ошибка при создании бота {error}')
        sys.exit()
    current_timestamp = int(time.time())
    status = 'Проект пока не проверяется.'
    while True:
        try:
            response = get_api_answer(ENDPOINT, current_timestamp)
            new_status = check_response(response)
            if new_status != status and new_status != []:
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
