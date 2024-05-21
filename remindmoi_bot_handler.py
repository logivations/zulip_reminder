import json
import logging
from typing import Any, Dict

import requests
import urllib3

from bot_helpers import (REMOVE_ENDPOINT,
                         LIST_ENDPOINT,
                         parse_remove_command_content,
                         generate_reminders_list,
                         is_set_timezone,
                         set_timezone, SET_TIMEZONE, parse_cmd, get_path, WHO_ENDPOINT, generate_who_list)

USAGE = '''
The first step is to set timezone:
For example:
`set timezone Europe/Kiev`
`set timezone Europe/Berlin`

To find out who the creator of a reminder in a stream is, write `who #stream_name` to the bot:
``who #general``
It works only for stream reminders, personally reminders are protected

To store a reminder, write a private message to chat with the bot 
or if you are in another chat then start your message with the mention of a reminder, like ``@reminder ...``

You can create a reminder to yourself, to some person, or for a stream.
You can create one-time or recurring reminders.


The available command for whom:
``me``, ``here``, ``@user``, ``#stream``


Available time to positive number: minutes, hours, days, weeks, minute, hour, day, week
If you want to remind some large text or in the text will be date format please highlight with double-quotes.
``me to "SOME LARGE TEXT OR WITH DATE FORMAT" on September 10 at 12:00``


Few examples of simple reminders to yourself:
```me to update Jira in 3 hours```
```me about Happy Birthday!! on June 1 at 10:00```
```me go home today at 19:00```
```me call with the team tomorrow at 10:00```
```me some text in 1 week``` will be a reminder after 1 week at the time it was created or add your time ```at 10:00```
and many other date formats.

Few examples for someone:
```@user to hello in 1 minute```
```@user to hello on Monday at 15:00```
```here about update your hours on 1st of July at 17:00```
```#stream text TIME```
etc.

Few examples of interval reminders:
```me to log hours every day at 10:00```
```#stream to standup every Monday, Tuesday and Friday at 11:00``` will be sent to default topic ```reminder```,
If you want to send reminder on a specific topic then create a reminder inside the stream
```#stream to update your issues every weekday at 10:00```
```here about some text repeat every Monday at 10:00```
```@user some text TIME```
```#stream about Estimation every 2nd week at 15:00 start on Monday```
```#stream about text every 2nd week at 15:00 start on June 2```
with end date
````#stream text every week at 15:00 start on Monday end on 2 June````
or you can add reminder for every last or first day of the month
```<to> <some text> every last day of the month``` will be every last day at 9:00 or 
 if you need to set time ```<to> <some text> every last day of the month at 15:00```


To remove a reminder:
```remove <reminder_id>```
``remove 2``

To list reminders:
```list```
'''
urllib3.disable_warnings()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class RemindMoiHandler:

    @staticmethod
    def usage() -> str:
        return USAGE

    def handle_message(self, message: Dict[str, Any], bot_handler: Any) -> None:
        bot_response = get_bot_response(message, bot_handler)
        bot_handler.send_reply(message, bot_response)


def get_bot_response(message: Dict[str, Any], bot_handler: Any):
    content = message["content"]
    if content.startswith(('help', '?', 'halp')):
        return USAGE
    try:

        if is_set_timezone(content):
            request = set_timezone(content, message["sender_email"])
            response = requests.post(url=SET_TIMEZONE, json=request)
            response = response.json()
            assert response["success"]
            return "Thanks"

        if content.startswith("remove"):
            reminder_id = parse_remove_command_content(content, message["sender_email"])
            response = requests.post(url=REMOVE_ENDPOINT, json=reminder_id)
            response = response.json()
            return "Reminder deleted." if response['success'] else "It is not your reminder"
        if content.startswith("list"):
            zulip_user_email = {"zulip_user_email": message["sender_email"]}
            response = requests.post(url=LIST_ENDPOINT, json=zulip_user_email)
            response = response.json()

            assert response["success"]
            return generate_reminders_list(response["reminders_list"])

        if content.startswith("who"):
            stream_name = " ".join(content.split()[1::])
            response = requests.get(url=WHO_ENDPOINT, params=dict(stream_name=stream_name))
            response = response.json()
            if response["success"]:
                reminders = response["reminders"]
                return generate_who_list(reminders) if reminders else "No reminders for this stream"
            return response["error"]

        text, date, to, is_stream, is_interval, prefix, raw_to, is_use_timezone = parse_cmd(message)
        if is_stream and message.get("stream_id", False):
            to = message["stream_id"]
        topic = message["subject"] if message["type"] == "stream" else "reminder" if is_stream else None
        url = get_path(to, is_interval, is_stream)
        text_date = "every " + " ".join(date) if isinstance(date, list) \
                    else date.strftime("every %A at %H:%M") if is_interval \
                    else date.strftime(f"on %b %d at %H:%M")
        reminder = {
            "zulip_user_email": message.get("sender_email"),
            "text": text,
            "created": str(message.get("timestamp")),
            "to": to,
            "time": date if isinstance(date, list) else date.strftime("%Y-%m-%d %H:%M"),
            "is_stream": is_stream,
            "topic": topic,
            "is_interval": is_interval,
            "full_content": content,
            "text_date": text_date,
            "is_use_timezone": is_use_timezone,
        }
        response = requests.post(url=url, json=reminder,
                                 headers={"Content-Type": "application/json; charset=utf-8"}).json()

        response_to = "you" if raw_to == "me" else raw_to
        if not response["success"]:
            return response["result"]
        return_message = f'I will remind {response_to} {prefix} "{text}" {text_date}. Reminder id {response["result"]}'
        return return_message

    except requests.exceptions.ConnectionError:
        logger.warning("Server not running")
        return "Server not running, call Pavlo Y."
    except (TypeError, KeyError) as e:
        logger.warning(f"TypeError|KeyError {e}")
        return "Invalid input. Please check help."
    except json.JSONDecodeError as e:
        logger.warning(f"JSONDecodeError {e}")
        return "Something went wrong"
    except Exception as e:
        logger.error(f"Exception {e}")
        return "Something went wrong. Call Pavlo Y."


handler_class = RemindMoiHandler
