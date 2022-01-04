import json
import requests
import urllib3
from typing import Any, Dict

from bot_helpers import (ADD_ENDPOINT,
                         REMOVE_ENDPOINT,
                         LIST_ENDPOINT,
                         REPEAT_ENDPOINT,
                         MULTI_REMIND_ENDPOINT,
                         is_add_command,
                         is_remove_command,
                         is_list_command,
                         is_repeat_reminder_command,
                         is_multi_remind_command,
                         parse_add_command_content,
                         parse_remove_command_content,
                         generate_reminders_list,
                         parse_repeat_command_content,
                         parse_multi_remind_command_content, is_add_on_date_command, parse_add_on_date_command_content,
                         is_add_to_another, parse_add_command_to_content, ADD_TO_ENDPOINT, is_set_timezone,
                         set_timezone, SET_TIMEZONE)


USAGE = '''
A bot that schedules reminders for users.

First step it is set timezone:
For example:
`set timezone Europe/Kiev`
`set timezone Europe/Berlin`


To store a reminder, mention or send a message to the bot in the following format:

`add int <positive number> <about>`

`add 1 day clean the dishes`
`add 10 hours eat`

Available time to positive number: minutes, hours, days, weeks, minute, hour, day, week


`add <date> <about>`
`add 2021/10/25 10:30 call with Tim`
`add 2022-01-22 15:00 drink water`

Add to some person

`add to <@user_name> about <text> at <date>'

`add to @Petro Gryb about in 10 minutes the beginning at 2021-10-22 11:20`
`add to @Harry Potter about he is coming at 10 minutes`
Available time to positive number: minutes, hours, days, weeks, minute, hour, day, week or time with date

To repeat a reminder: 
`repeat <@user or stream> about <some text> every <day> at <time>`
`repeat <@user or stream> about <some text> every <interval>`

Available <user or stream> is: @username, stream_name, me, here
Available interval is : minute, hour, day, week, month, minutes, hours, days, weeks, months
`repeat @user_name about stand up with team every Friday at 12:30`


`repeat me about text every Friday at 12:30`
`repeat name_stream about text Friday at 13:00'

`repeat me about don`t forget drink water every 30 minutes`

To remove a reminder:
`remove <reminder_id>`

To list reminders:
`list`
'''
urllib3.disable_warnings()


class RemindMoiHandler:

    @staticmethod
    def usage() -> str:
        return USAGE

    def handle_message(self, message: Dict[str, Any], bot_handler: Any) -> None:
        bot_response = get_bot_response(message, bot_handler)
        bot_handler.send_reply(message, bot_response)


def get_bot_response(message: Dict[str, Any], bot_handler: Any) -> str:
    if message["content"].startswith(('help', '?', 'halp')):
        return USAGE
    try:
        if is_add_on_date_command(message["content"]):
            reminder_object = parse_add_on_date_command_content(message)
            response = requests.post(url=ADD_ENDPOINT, json=reminder_object)
            response = response.json()
            assert response["success"]
            if response.get("timezone"):
                return response["timezone"]
            return f"Reminder stored. Your reminder id is: {response['reminder_id']}"
        if is_add_command(message["content"]):
            reminder_object = parse_add_command_content(message)
            response = requests.post(url=ADD_ENDPOINT, json=reminder_object)
            response = response.json()
            assert response['success']
            return f"Reminder stored. Your reminder id is: {response['reminder_id']}"
        if is_add_to_another(message["content"]):
            reminder_obj = parse_add_command_to_content(message)
            if isinstance(reminder_obj, str):
                return reminder_obj
            response = requests.post(url=ADD_TO_ENDPOINT, json=reminder_obj)
            response = response.json()
            assert response['success']
            if response.get("timezone"):
                return response["timezone"]
            return f"Reminder stored. Your reminder id is: {response['reminder_id']}"
        if is_remove_command(message["content"]):
            reminder_id = parse_remove_command_content(message["content"], message["sender_email"])
            response = requests.post(url=REMOVE_ENDPOINT, json=reminder_id)
            response = response.json()
            return "Reminder deleted." if response['success'] else "It is not your reminder"
        if is_list_command(message["content"]):
            zulip_user_email = {"zulip_user_email": message["sender_email"]}
            response = requests.post(url=LIST_ENDPOINT, json=zulip_user_email)
            response = response.json()
            assert response["success"]
            return generate_reminders_list(response)
        if is_repeat_reminder_command(message["content"]):
            repeat_request = parse_repeat_command_content(message)
            if isinstance(repeat_request, str):
                return repeat_request
            response = requests.post(url=REPEAT_ENDPOINT, json=repeat_request)
            response = response.json()
            assert response["success"]
            if response.get("timezone"):
                return response["timezone"]
            return f"Reminder will be repeated every {' '.join(repeat_request['time'])}.\n" \
                   f"Reminder id: {response['reminder_id']}"
        if is_set_timezone(message["content"]):
            request = set_timezone(message["content"], message["sender_email"])
            print("here")
            response = requests.post(url=SET_TIMEZONE, json=request)
            response = response.json()
            assert response["success"]
            return "Thanks"
        # if is_multi_remind_command(message["content"]):
        #     multi_remind_request = parse_multi_remind_command_content(message["content"])
        #     response = requests.post(url=MULTI_REMIND_ENDPOINT, json=multi_remind_request)
        #     response = response.json()
        #     assert response["success"]
        #     return f"Reminder will be sent to the specified recipients."  # Todo: add list of recepients
        return "Invalid input. Please check help."
    except requests.exceptions.ConnectionError:
        return "Server not running, call Pavlo Y."
    except (json.JSONDecodeError, AssertionError):
        return "Something went wrong"
    except OverflowError:
        return "What's wrong with you?"
    except Exception as e:
        print(e)
        return "Something went wrong. Call Pavlo Y."


handler_class = RemindMoiHandler
