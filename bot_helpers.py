import logging
import re
from datetime import timedelta, datetime
from typing import Dict, Any

from dateparser.search import search_dates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

UNITS = ['minutes', 'hours', 'days', 'weeks']
SINGULAR_UNITS = ['minute', 'hour', 'day', 'week']
ARGS_WEEK_DAY = {
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday"
}

ENDPOINT_URL = "http://127.0.0.1:8000"
ADD_ENDPOINT = ENDPOINT_URL + '/add_reminder'
REMOVE_ENDPOINT = ENDPOINT_URL + '/remove_reminder'
LIST_ENDPOINT = ENDPOINT_URL + '/list_reminders'
REPEAT_ENDPOINT = ENDPOINT_URL + '/repeat_reminder'
ADD_TO_ENDPOINT = ENDPOINT_URL + "/add_to"
SET_TIMEZONE = ENDPOINT_URL + "/timezone"
send_to = {"me": lambda x, o: (x, o["sender_id"]),
           "here": lambda x, o: (True, o["stream_id"]) if o["type"] == "stream" else send_to["me"](x, o)}


def parse_cmd(message: dict) -> tuple:
    content: str = message["content"]
    command = content.split()

    is_stream, to, raw_to = parse_send_to(command, message)
    prefix = parse_prefix(command)
    is_marked = content.count('"') == 2
    if is_marked:
        text, command = parse_marked_text(command)

    date, is_interval, is_use_timezone = parse_date(command)
    if not is_marked:
        text = parse_text(command)
    return text, date, to, is_stream, is_interval, prefix, raw_to, is_use_timezone


def parse_prefix(message: list) -> str:
    prefix = ""
    if message[0] in ("to", "about"):
        prefix = message.pop(0)
    return prefix


def parse_date(cmd: list) -> tuple:
    text = " ".join(cmd)
    is_use_timezone = True
    index_dict = dict((value, index) for index, value in enumerate(cmd))
    if re.search(r"every (last|first) day of the month", text):
        is_interval = True
        every_idx = index_dict["every"]
        date = cmd[every_idx + 1::]
        del cmd[every_idx::]
        return date, is_interval, is_use_timezone
    if re.search(r"every ((\d(th|nd|rd)|\d) month|month)", text):
        is_interval = True
        every_idx = index_dict["every"]
        date = cmd[every_idx + 1::]
        del cmd[every_idx::]
        return date, is_interval, is_use_timezone
    if "repeat every" in text:
        is_interval = True
        rep_idx, every_idx = index_dict["repeat"], index_dict["every"]
        date = cmd[every_idx + 1::]
        del cmd[rep_idx::]
        return date, is_interval, is_use_timezone
    if "every weekday" in text:
        is_interval = True
        every_idx = index_dict["every"]
        date = cmd[every_idx + 1::]
        del cmd[every_idx::]
        return date, is_interval, is_use_timezone
    text_with_date = search_dates(text, settings={"PREFER_DATES_FROM": "current_period"})
    if text_with_date is None and "every" in cmd:
        every_idx = index_dict["every"]
        date = cmd[every_idx + 1::]
        del cmd[every_idx::]
        is_interval = True
        return date, is_interval, is_use_timezone
    list_text_date = ' '.join([i[0] for i in text_with_date]).split()
    if "in" in list_text_date:
        is_use_timezone = False
    if index_dict.get("every") is not None and (any(i in cmd for i in SINGULAR_UNITS + UNITS) or sum(
            1 for i in cmd[index_dict["every"]::] if i.lower().replace(",", "") in ARGS_WEEK_DAY) > 1):
        is_interval = True
        every_idx = index_dict["every"]
        date = cmd[every_idx + 1::]
        del cmd[every_idx::]
        return date, is_interval, is_use_timezone
    date: datetime = text_with_date[-1][-1]
    date_indexes = [index_dict[i] for i in list_text_date]
    is_interval = True if cmd[date_indexes[0] - 1] == "every" else False

    if is_interval:
        date_indexes.insert(0, date_indexes[0] - 1)
    del cmd[date_indexes[0]:date_indexes[-1] + 1]

    if (date + timedelta(hours=1)) < datetime.now():

        if re.match(r"at\s\d{2}:\d{2}", text_with_date[-1][0]) is not None:
            period = {"days": 1}
            logging.info(f"Add day to date, past time is {date}")
        else:
            period = {"weeks": 1}
            logging.info(f"Add week to date, past time is {date}")

        date += timedelta(**period)
    if date.hour == 0:
        date += timedelta(hours=9)
    return date, is_interval, is_use_timezone


def parse_send_to(content: list, message: dict) -> tuple:
    is_stream = False
    if content[0].startswith("@"):
        to = [content.pop(0), content.pop(0)]
        return is_stream, to, " ".join(to)
    if content[0].startswith("#"):
        is_stream = True
        to = parse_stream_name(content)
        return is_stream, to, to
    to = content.pop(0).lower()
    return *send_to[to](is_stream, message), to


def parse_stream_name(text: list) -> str:
    if text[0].endswith("**"):
        return text.pop(0)
    last_index = None
    for idx, i in enumerate(text[1:]):
        if i.endswith("**"):
            last_index = idx + 1
            break
    stream_name = " ".join(text[:last_index + 1])
    del text[:last_index + 1]
    return stream_name


def parse_text(message: list) -> str:
    return " ".join(message)


def parse_marked_text(message: list) -> tuple:
    message = " ".join(message)
    start, end = message.find('"'), message.rfind('"')
    text = message[start + 1:end]
    message = " ".join(message.replace('"', "").split(text)).strip().split()
    return text, message


def get_path(to, is_interval: bool, is_stream: bool) -> str:
    if is_interval:
        return REPEAT_ENDPOINT
    if isinstance(to, list) or is_stream:
        return ADD_TO_ENDPOINT
    return ADD_ENDPOINT


def is_set_timezone(content: str) -> bool:
    try:
        command = content.split()
        assert command[0] == "set"
        assert command[1] == "timezone"
        return True
    except:
        return False


def set_timezone(content, email) -> dict:
    timezone = content.split()[-1]
    return {"timezone": timezone, "email": email}


def parse_remove_command_content(content: str, email: str) -> Dict[str, Any]:
    command = content.split(' ')
    return {'id': command[1], "email": email}


def generate_reminders_list(reminders: dict) -> str:
    active_reminders = []
    completed_reminders = []
    for reminder in reminders:
        if reminder["active"]:
            active_reminders.append(reminder)
            continue
        completed_reminders.append(reminder)
    text = "Completed reminders 😴😪: \n" if completed_reminders else ""
    for i in completed_reminders:
        text += f"- {i['content']}. Was on {i['text_date']}.   Reminder id {i['id']}\n"

    text += "\nUncompleted reminders 🏃: \n" if active_reminders else ""
    for i in active_reminders:
        text += f"- {i['content']}.   Reminder id {i['id']}\n"

    if not text:
        text = "You don`t have reminders!"
    return text
