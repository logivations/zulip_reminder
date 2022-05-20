import datetime
import json
import logging
import os
from math import modf
from typing import Optional

import databases
import pytz
import urllib3
import zulip
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dateparser.search import search_dates
from dateutil import parser
from fastapi import FastAPI, Body
from sqlalchemy import and_
from starlette.responses import JSONResponse

from models import DATABASE_URL, reminders, intervals, timezone, Reminder, Email, Remove

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

urllib3.disable_warnings()

database = databases.Database(DATABASE_URL)
jobstores = {
    "default": SQLAlchemyJobStore(url=DATABASE_URL)
}
ZULIPRC = os.path.abspath(os.path.join(os.path.dirname(__file__), 'zuliprc'))
schedule = AsyncIOScheduler(jobstores=jobstores)
schedule.start()
client = zulip.Client(config_file=ZULIPRC)
ARGS_WEEK_DAY = {
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday"
}
DAY_DICT = {"monday": "mon", "tuesday": "tue", "wednesday": "wed", "thursday": "thu", "friday": "fri",
            "saturday": "sat", "sunday": "sun"}
ARGS_INTERVAL = {"minute", "hour", "day", "week", "month", "minutes", "hours", "days", "weeks", "months"}
FREQUENCY = {"second": 2, "2nd": 2, "2": 2, "3": 3, "two": 2, "three": 3, "3rd": 3, "third": 3}
app = FastAPI()


@app.get("/")
async def test():
    return "Test!!!"


@app.on_event("startup")
async def startup():
    await database.connect()
    app.current_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo.utcoffset(None)


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


def convert_zone(zone: float):
    minutes, hour = modf(zone)
    minutes *= 60
    return hour, minutes


def reminder_insert_expression(reminder: Reminder):
    return reminders.insert().values(
        zulip_user_email=reminder.zulip_user_email,
        text=reminder.text,
        created=reminder.created,
        is_interval=reminder.is_interval,
        is_stream=reminder.is_stream,
        stop_date=reminder.time,
        active=reminder.active,
        full_content=reminder.full_content,
        topic=reminder.topic,
        to=reminder.to,
        text_date=reminder.text_date,
    )


@app.post("/add_reminder", response_class=JSONResponse)
async def add_reminder(request: Reminder):
    logger.info(f"Simple reminder from {request.zulip_user_email}")
    zone = await get_timezone(request.zulip_user_email)
    if zone is None:
        return {"success": False, "result": "Set timezone, see help"}
    hour, minutes = convert_zone(zone)
    time = parser.parse(request.time) + datetime.timedelta(hours=hour, minutes=minutes)
    request.time = time.timestamp()

    query = reminder_insert_expression(request)

    last_record_id = await database.execute(query)
    schedule.add_job(
        send_reminder_to_me,
        "date",
        run_date=time,
        args=[last_record_id],
        id=str(last_record_id)
    )
    return {"success": True, "result": last_record_id}


async def get_reminder_by_id(reminder_id: int):
    query = reminders.select().where(reminders.c.id == reminder_id)
    return await database.fetch_one(query=query)


async def send_reminder_to_me(reminder_id: int):
    reminder = await get_reminder_by_id(reminder_id)
    text = f"Reminder: :siren: {reminder.text}"
    request = {
        "type": "private",
        "to": reminder.zulip_user_email,
        "content": text
    }
    result = send_zulip_reminder(request)
    if result:
        update_active = reminders.update().where(reminders.c.id == reminder.id)
        await database.execute(update_active, values={"active": 0})
        logger.info(f"Success sent to {reminder.zulip_user_email}, id = {reminder_id}")
    return result


@app.post("/list_reminders", response_class=JSONResponse)
async def list_reminders(request: Email):
    response_reminders = []
    # query = "SELECT * FROM reminders WHERE zulip_user_email = :zulip_user_email"
    query = reminders.select().where(reminders.c.zulip_user_email == request.zulip_user_email)
    user_reminders = await database.fetch_all(query)
    for reminder in user_reminders:
        data = {
            "id": reminder.id,
            "content": reminder.full_content,
            "active": reminder.active,
            "text_date": reminder.text_date,
        }
        response_reminders.append(data)
    return {"success": True, "reminders_list": response_reminders}


@app.post("/remove_reminder", response_class=JSONResponse)
async def remove_reminder(request: Remove):
    query = reminders.select().where(
        and_(
            reminders.c.id == request.id, reminders.c.zulip_user_email == request.email
        )
    )

    reminder = await database.fetch_one(query=query)
    if not reminder:
        return {"success": False}
    if reminder.is_interval:
        await database.execute(intervals.delete(intervals.c.reminder_id == reminder.id))
    try:
        schedule.remove_job(str(reminder.id))
    except JobLookupError as e:
        logger.info(f"{e}, probably that job is finished")
    await database.execute(reminders.delete(reminders.c.id == reminder.id))
    return {"success": True}


@app.post("/repeat_reminder", response_class=JSONResponse)
async def repeat_reminder(request: Reminder):
    logger.info(f"Interval reminder from {request.zulip_user_email}")
    zone = await get_timezone(request.zulip_user_email)
    if zone is None:
        return {"success": False, "timezone": "Set timezone, see help"}
    time = request.time
    task = {}
    request.time = None
    trigger = "cron"

    if isinstance(request.to, list):
        user = " ".join(request.to).replace("@", "").replace("**", "")
        to = await get_user(user)
    elif request.is_stream:
        to = request.to \
            if isinstance(request.to, int) \
            else client.get_stream_id(request.to.replace("#", "").replace("**", ""))["stream_id"]
    else:
        to = request.to
    request.to = to

    if isinstance(time, list):
        task, trigger = get_time_from_list(time, task, zone)
    if isinstance(time, str):
        hour, minutes = convert_zone(zone)
        time = parser.parse(time) + datetime.timedelta(hours=hour, minutes=minutes)
        task["day_of_week"] = time.weekday()
        task["hour"] = time.hour
        task["minute"] = time.minute

    query = reminder_insert_expression(request)
    last_record_id = await database.execute(query)
    interval_query = intervals.insert().values(
        reminder_id=last_record_id,
        interval_time=json.dumps(task, default=str)
    )
    await database.execute(interval_query)
    task.update(dict(
        args=[last_record_id, to, request.is_stream, request.topic],
        id=str(last_record_id)))

    schedule.add_job(
        send_interval_reminder,
        trigger,
        **task
    )
    return {"success": True, "result": last_record_id}


def get_time_from_list(time: list, task: dict, zone):
    if is_last_or_first_day_moth(time):
        time[0] = time[0] if time[0] == "last" else 1
        if all(i in time for i in ("day", "month")):
            return {"year": "*", "month": "*", "day": time[0]}, "cron"
    if any(i in ARGS_INTERVAL for i in time):
        return get_interval_time(time, task, zone)

    if sum(1 for i in time if i.lower().replace(",", "") in ARGS_WEEK_DAY) > 1:
        return get_multiple_day_time(time, task, zone)
    if "weekday" in time:
        days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        idx = time.index("weekday")
        time[idx:idx] = days
        time.remove("weekday")
        return get_multiple_day_time(time, task, zone)
    logger.warning(f"Time from list, unsupported type: {time}")


def is_last_or_first_day_moth(time):
    return time[0] in {"last", "first", "1st"}


def get_multiple_day_time(time: list, task: dict, zone: float):
    hour, minute = convert_zone(zone)
    days = []
    time_idx = None
    for idx, i in enumerate(time):
        i = i.replace(",", "").lower()
        if i == "at":
            time_idx = idx
        if DAY_DICT.get(i) is not None:
            days.append(DAY_DICT[i])
    time = time[time_idx + 1]
    date = datetime.datetime.strptime(time, "%H:%M")
    date = date + datetime.timedelta(hours=hour, minutes=minute)
    task["day_of_week"] = ",".join(days)
    task["hour"] = date.hour
    task["minute"] = date.minute
    trigger = "cron"
    return task, trigger


def get_interval_time(time: list, task: dict, zone):
    try:
        frequency = int(time[0])
    except ValueError:
        frequency = FREQUENCY.get(time[0], 1)

    idx = 0 if frequency == 1 else 1
    if time[idx] in ARGS_INTERVAL:
        interval = time[idx] if time[idx].endswith('s') else time[idx] + "s"
        task[interval] = frequency
    if len(time) == idx + 1:
        time.append("at 9:00")
    time = time[idx + 1::]
    time, start = find_start_end(time, "start")
    start, end = find_start_end(start, "end")
    tuple_date = search_dates(" ".join(time), settings={"PREFER_DATES_FROM": "current_period"})
    hour, minute = convert_zone(zone)
    date: datetime = tuple_date[0][1] + datetime.timedelta(hours=hour, minutes=minute)
    hours = date.hour
    minutes = date.minute
    if start:
        start_date = search_dates(" ".join(start))[-1][-1]

        start_date = start_date.replace(hour=hours, minute=minutes, second=0)
        task["start_date"] = start_date
    else:
        date = date if date > datetime.datetime.now() else date + datetime.timedelta(**task)
        task["start_date"] = date
    if end:
        end_date = search_dates(" ".join(end))[-1][-1]
        end_date = end_date.replace(hour=hours, minute=minutes, second=0)
        task["end_date"] = end_date

    trigger = "interval"
    return task, trigger


def find_start_end(time: list, value: str):
    try:
        idx = time.index(value)
        return time[:idx], time[idx + 1:]
    except ValueError:
        return time, []


async def send_interval_reminder(reminder_id: int, to: int, is_stream: bool, topic: Optional[str] = None):
    reminder = await get_reminder_by_id(reminder_id)
    content = f"Reminder: {reminder.text}"
    message = {
        "type": "stream" if is_stream else "private",
        "to": [to],
        "content": content
    }
    if is_stream:
        message["topic"] = topic
    result = send_zulip_reminder(message)
    if result:
        logger.info(f"Success sent to {to}, id = {reminder_id}")


def send_zulip_reminder(message: dict):
    response = client.send_message(message)
    logger.info(f"{response}")
    return response['result'] == 'success'


@app.post("/add_to", response_class=JSONResponse)
async def add_reminder_to_person(request: Reminder):
    logger.info(f"Reminder to someone from {request.zulip_user_email}")
    zone = await get_timezone(request.zulip_user_email)
    if zone is None:
        return {"success": False, "result": "Set timezone, see help"}
    hour, minutes = convert_zone(zone)
    time = parser.parse(request.time) + datetime.timedelta(hours=hour, minutes=minutes)
    request.time = time.timestamp()
    if request.is_stream:
        try:
            to = request.to if isinstance(request.to, int) else client.get_stream_id(request.to)["stream_id"]
        except KeyError:
            return {"success": False, "result": "Invite reminder to stream or create reminder inside stream"}
    else:
        name = " ".join(request.to).replace("@", "").replace("**", "")
        to = await get_user(name)

    request.to = to
    query = reminder_insert_expression(request)
    last_record_id = await database.execute(query)
    schedule.add_job(
        send_reminder_to,
        "date",
        run_date=time,
        args=[last_record_id, to],
        id=str(last_record_id)
    )
    return {"success": True, "result": last_record_id}


async def send_reminder_to(reminder_id, to):
    reminder = await get_reminder_by_id(reminder_id)
    text = f"Reminder: :siren: {reminder.text}"
    request = {
        "type": "private" if not reminder.is_stream else "stream",
        "to": [to],
        "content": text
    }
    if reminder.is_stream:
        request["topic"] = reminder.topic
    result = send_zulip_reminder(request)
    if result:
        update_active = reminders.update().where(reminders.c.id == reminder.id)
        await database.execute(update_active, values={"active": 0})
        logger.info(f"Success sent to {to}, id = {reminder_id}")
    return result


@app.post("/timezone", response_class=JSONResponse)
async def set_timezone(request: dict = Body(...)):
    check = "SELECT * FROM timezones WHERE email = :email"
    user = await database.fetch_one(
        check, values={"email": request["email"]}
    )
    if user:
        query = timezone.update().values(
            zone=request["timezone"]
        ).where(timezone.c.id == user.id)
    else:
        query = timezone.insert().values(
            email=request["email"],
            zone=request["timezone"]
        )
    await database.execute(query)
    return {"success": True}


async def get_timezone(email):
    query = "SELECT zone FROM timezones WHERE email = :email"
    zone = await database.fetch_one(query=query, values={"email": email})
    if not zone:
        return
    return (app.current_timezone - datetime.datetime.now(
        pytz.timezone(zone[0])).utcoffset()).total_seconds() / 3600


async def get_user(full_name):
    members = client.get_members()['members']
    for user in members:
        if full_name == user["full_name"]:
            return user["email"]
