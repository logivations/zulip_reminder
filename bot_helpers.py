
from typing import Any, Dict
from datetime import timedelta, datetime

# from remindmoi_bot_handler import get_bot_response
import pytz

UNITS = ['minutes', 'hours', 'days', 'weeks']
SINGULAR_UNITS = ['minute', 'hour', 'day', 'week']
REPEAT_UNITS = ['weekly', 'daily', 'monthly'] + ['minutely']  # Remove after testing 

ENDPOINT_URL = "http://127.0.0.1:8000"#'http://localhost:8789'
ADD_ENDPOINT = ENDPOINT_URL + '/add_reminder'
REMOVE_ENDPOINT = ENDPOINT_URL + '/remove_reminder'
LIST_ENDPOINT = ENDPOINT_URL + '/list_reminders'
REPEAT_ENDPOINT = ENDPOINT_URL + '/repeat_reminder'
MULTI_REMIND_ENDPOINT = ENDPOINT_URL + '/multi_remind'
ADD_TO_ENDPOINT = ENDPOINT_URL + "/add_to"
SET_TIMEZONE = ENDPOINT_URL + "/timezone"
USER_TIMEZONE = {}


def is_add_command(content: str, units=UNITS + SINGULAR_UNITS) -> bool:
    """
    Ensure message is in form <COMMAND> reminder <int> UNIT <str>
    """
    try:
        command = content.split(' ', maxsplit=4)  # Ensure the last element is str

        assert command[0] == 'add'
        assert type(int(command[1])) == int
        assert command[2] in units
        assert type(command[3]) == str
        return True
    except (IndexError, AssertionError, ValueError):
        return False


def is_set_timezone(content: str):
    try:
        command = content.split()
        print(command)
        assert command[0] == "set"
        assert command[1] == "timezone"
        return True
    except:
        return False


def is_add_on_date_command(content: str):
    try:
        command = content.split(" ", maxsplit=3)

        date_str = " ".join([command[1], command[2]]).replace("/", "-")
        date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")

        assert command[0] == 'add'

        assert type(date) == datetime

        assert type(command[-1]) == str

        return True
    except (IndexError, AssertionError, ValueError):

        return False


def is_add_to_another(content: str):
    try:
        command = content.split(" ")
        assert command[0] == "add"
        assert command[1] == "to"
        assert command[2][0] == "@"
        return True
    except (IndexError, AssertionError, ValueError):
        return False


def is_remove_command(content: str) -> bool:
    try:
        command = content.split(' ')
        assert command[0] == 'remove'
        assert type(int(command[1])) == int
        return True
    except (AssertionError, IndexError, ValueError):
        return False


def is_list_command(content: str) -> bool:
    try:
        command = content.split(' ')
        assert command[0] == 'list'
        return True
    except (AssertionError, IndexError, ValueError):
        return False


def is_repeat_reminder_command(content: str) -> bool:
    try:
        command = content.split(' ')
        assert command[0] == 'repeat'
        assert type(command[1]) == str
        return True
    except (AssertionError, IndexError, ValueError):
        return False


# not realized
def is_multi_remind_command(content: str) -> bool:
    try:
        command = content.split(' ', maxsplit=2)
        assert command[0] == 'multiremind'
        assert type(int(command[1])) == int
        return True
    except (AssertionError, IndexError, ValueError):
        return False


def set_timezone(content, email):
    timezone = content.split()[-1]
    return {"timezone": timezone, "email": email}


def parse_add_on_date_command_content(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a message object with reminder details,
    construct a JSON/dict.
    """

    user = message['sender_email']
    content = message['content'].split(' ', maxsplit=3)  # Ensure the last element is str
    date_str = " ".join([content[1], content[2]]).replace("/", "-")
    date = datetime.strptime(date_str, "%Y-%m-%d %H:%M").astimezone()
    return {"zulip_user_email": user,
            "title": content[3],
            "created": message['timestamp'],
            "deadline": date.timestamp(),
            "active": 1,
            "on_date": True}


def parse_add_command_content(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a message object with reminder details,
    construct a JSON/dict.
    """
    content = message['content'].split(' ', maxsplit=3)  # Ensure the last element is str

    return {"zulip_user_email": message['sender_email'],
            "title": content[3],
            "created": message['timestamp'],
            "deadline": compute_deadline_timestamp(message['timestamp'], content[1], content[2]),
            "active": 1}


def parse_remove_command_content(content: str, email: str) -> Dict[str, Any]:
    command = content.split(' ')
    return {'id': command[1], "email": email}


def parse_repeat_command_content(content: dict) -> Dict[str, Any]:
    command = content["content"].split(' ')
    stream = False
    if command[1].startswith("@"):
        to = " ".join(command[1:3]).replace("@", "").replace("*", "")
    elif command[1] == "me":
        to = content["sender_email"]
    else:
        to = command[1] if command[1] != "here" else content["display_recipient"]
        stream = True
    try:
        index_about = -find_index(command, "about") - 1
        index_every = -find_index(command, "every") - 1
    except TypeError:
        return f"{content['sender_full_name']} you forgot to use about or every"
    title = " ".join(command[index_about + 1:index_every])
    topic = content["subject"]
    when = command[index_every + 1::]

    return {'to': to,
            'title': title,
            "time": when,
            "topic": topic,
            "zulip_user_email": content["sender_email"],
            "created": content['timestamp'],
            "is_stream": stream
            }


def find_index(l, el):
    for index, i in enumerate(l[::-1]):
        if i == el:
            return index


def parse_multi_remind_command_content(content: str) -> Dict[str, Any]:
    """
    multiremind 23 @**Jose** @**Max** ->
    {'reminder_id': 23, 'users_to_remind': ['Jose', Max]}
    """
    command = content.split(' ', maxsplit=2)
    users_to_remind = command[2].replace('*', '').replace('@', '').split(' ')
    return {'reminder_id': command[1],
            'users_to_remind': users_to_remind}


def generate_reminders_list(response: Dict[str, Any]) -> str:
    bot_response = "Current:"

    completed = "Completed:"
    reminders_list = response['reminders_list']
    if not reminders_list:
        return 'No reminders avaliable.'

    for reminder in reminders_list:
        if not reminder.get("active"):
            completed += f"""
        \nReminder id {reminder['reminder_id']} is scheduled on {reminder['deadline'][:-7] if reminder.get("deadline")
            else reminder["repeat"]}\n About: {reminder['title']}
        """
            continue
        if reminder.get("repeat"):
            bot_response += f"""
                    \nReminder id {reminder['reminder_id']} is repeated every {reminder['repeat']}\n About: {reminder['title']}
                    """
            continue
        bot_response += f"""
        \nReminder id {reminder['reminder_id']} is scheduled on {reminder['deadline'][:-7]}\n About: {reminder['title']}
        """
    result = completed + "\n" + "==" * 50 + "\n" + bot_response
    return result


def compute_deadline_timestamp(timestamp_submitted: str, time_value: int, time_unit: str) -> str:
    """
    Given a submitted stamp and an interval,
    return deadline timestamp.
    """
    if time_unit in SINGULAR_UNITS:  # Convert singular units to plural
        time_unit = f"{time_unit}s"
    interval = timedelta(**{time_unit: int(time_value)})
    datetime_submitted = datetime.fromtimestamp(timestamp_submitted)
    return (datetime_submitted + interval).timestamp()


def parse_add_command_to_content(content: dict):

    data = content["content"].split(" ")

    try:
        index_at = -find_index(data, "at") - 1
        index_about = -find_index(data, "about") - 1
    except TypeError:
        return f"{content['sender_full_name']} you forgot to use about or at"
    name = " ".join(data[2:index_about])
    to = name.replace("@", "").replace("*", "")
    title = " ".join(data[5:index_at])
    time = data[index_at + 1::]
    if time[-1] in UNITS + SINGULAR_UNITS:
        date = compute_deadline_timestamp(content['timestamp'], time[0], time[1])
    else:
        date = datetime.strptime(" ".join(time).replace("/", "-"), "%Y-%m-%d %H:%M").timestamp()
    return {"to": to,
            "title": title,
            "deadline": date,
            "active": 1,
            "zulip_user_email": content["sender_email"],
            "created": content['timestamp'],
            }
