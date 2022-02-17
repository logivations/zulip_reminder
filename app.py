import datetime
import os
from typing import Optional

import databases
import pytz
import urllib3
import zulip
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Body
from pydantic import BaseModel, EmailStr
from sqlalchemy import and_
from starlette.responses import JSONResponse

from models import DATABASE_URL, reminders, intervals, timezone
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
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
    "saturday": 5, "sunday": 6, "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
    "Friday": 4, "Saturday": 5, "Sunday": 6
}
ARGS_INTERVAL = {"minute", "hour", "day", "week", "month", "minutes", "hours", "days", "weeks", "months"}


class Email(BaseModel):
    zulip_user_email: EmailStr


class Remove(BaseModel):
    id: int
    email: EmailStr


class Reminder(BaseModel):
    zulip_user_email: EmailStr
    title: str
    created: datetime.datetime
    deadline: Optional[datetime.datetime] = None
    active: int = 1
    to: Optional[str] = None
    time: Optional[list] = None
    topic: Optional[str] = None
    is_stream: Optional[bool] = False
    on_date: Optional[bool] = False


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


@app.post("/add_reminder", response_class=JSONResponse)
async def add_reminder(request: Reminder):
    if request.on_date:
        zone = await get_timezone(request.zulip_user_email)
        if not zone:
            return {"success": True, "timezone": "Set timezone, see help"}
        time = request.deadline - zone
    else:
        time = request.deadline
    query = reminders.insert().values(
        zulip_user_email=request.zulip_user_email,
        title=request.title,
        created=request.created,
        deadline=time,
        active=request.active
    )

    last_record_id = await database.execute(query)
    schedule.add_job(
        send_private_zulip_reminder,
        "date",
        run_date=time,
        args=[last_record_id],
        id=str(last_record_id)
    )
    return {"success": True, "reminder_id": last_record_id}


@app.post("/list_reminders", response_class=JSONResponse)
async def list_reminders(request: Email):
    response_reminders = []
    query = "SELECT * FROM reminders WHERE zulip_user_email = :zulip_user_email"
    user_reminders = await database.fetch_all(
        query, values={"zulip_user_email": request.zulip_user_email}
    )
    interval_reminders = {}
    for reminder in user_reminders:
        if not reminder.deadline:
            interval_reminders[reminder.id] = {
                "title": reminder.title,
                "reminder_id": reminder.id,
                "active": reminder.active
            }
            continue
        response_reminders.append(
            {
                "title": reminder.title,
                "deadline": reminder.deadline,
                "reminder_id": reminder.id,
                "active": reminder.active
            }
        )
    if interval_reminders:
        ids = [i for i in interval_reminders.keys()]
        query_2 = intervals.select().filter(intervals.c.reminder_id.in_(ids))
        dates = await database.fetch_all(query_2)
        for i in dates:
            interval_reminders[i["reminder_id"]]["repeat"] = i["interval_time"]
            response_reminders.append(interval_reminders[i["reminder_id"]])
    return {"success": True, "reminders_list": response_reminders}


@app.post("/remove_reminder", response_class=JSONResponse)
async def remove_reminder(request: Remove):
    # query = "SELECT * FROM reminders WHERE zulip_user_email = :email and id = :id"
    query = reminders.select().where(
        and_(
            reminders.c.id == request.id, reminders.c.zulip_user_email == request.email
        )
    )

    reminder = await database.fetch_one(query=query)
    if not reminder:
        return {"success": False}
    if not reminder.deadline:
        await database.execute(intervals.delete(intervals.c.reminder_id == reminder.id))
    schedule.remove_job(str(reminder.id))
    await database.execute(reminders.delete(reminders.c.id == reminder.id))
    return {"success": True}


@app.post("/repeat_reminder", response_class=JSONResponse)
async def repeat_reminder(request: Reminder):
    query = reminders.insert().values(
        zulip_user_email=request.zulip_user_email,
        title=request.title,
        created=request.created,
        deadline=request.deadline,
        active=request.active
    )
    if "@" in request.to:
        to = request.to
    elif "#" in request.to:
        to = client.get_stream_id(request.to.replace("#", ""))
    else:
        to = await get_user(request.to)
    last_record_id = await database.execute(query)
    interval_query = intervals.insert().values(
        reminder_id=last_record_id,
        interval_time=" ".join(request.time)
    )
    await database.execute(interval_query)
    task = dict(
        args=[last_record_id, to, True],
        id=str(last_record_id))
    if request.is_stream:
        task["args"].append(request.topic)
        task["args"].append(request.is_stream)
    hour, minute, unit, value, day = await get_time(request.time)

    trigger = "cron"
    if value:
        task[unit] = value
        trigger = "interval"
    else:
        zone = await get_timezone(request.zulip_user_email)
        if zone is None:
            return {"success": True, "timezone": "Set timezone, see help"}
        task["day_of_week"] = day
        task["hour"] = int(hour) - int(str(zone)[0])  # hardcode
        task["minute"] = minute

    schedule.add_job(
        send_private_zulip_reminder,
        trigger,
        **task
    )
    return {"success": True, "reminder_id": last_record_id}


async def send_private_zulip_reminder(
        reminder_id: int, to: Optional[int] = None, is_repeat: Optional[bool] = False,
        topic: Optional[str] = None, is_stream: Optional[bool] = False

):
    query = "SELECT * FROM reminders WHERE id = :id"
    reminder = await database.fetch_one(query=query, values={"id": reminder_id})
    send_to = reminder.zulip_user_email if not to else to
    content = f"Don't forget: {reminder.title}. Reminder id: {reminder.id}"

    message = {
        "type": "private" if not is_stream else "stream",
        "to": send_to,
        "content": content
    }
    if not is_stream and not is_repeat and to:
        content = f"Don't forget: {reminder.title}. From {reminder.zulip_user_email}"
        message["content"] = content

    if is_stream:
        message["topic"] = topic
    response = client.send_message(message)
    if not is_stream and not is_repeat and not to:
        update_active = reminders.update()
        await database.execute(update_active, values={"active": 0})

    return response['result'] == 'success'


@app.post("/add_to", response_class=JSONResponse)
async def add_reminder_to_person(request: Reminder):
    zone = await get_timezone(request.zulip_user_email)
    if not zone:
        await get_timezone(request.zulip_user_email)
    time = request.deadline - zone
    query = reminders.insert().values(
        zulip_user_email=request.zulip_user_email,
        title=request.title,
        created=request.created,
        deadline=time,
        active=request.active
    )
    last_record_id = await database.execute(query)
    to = await get_user(request.to)
    schedule.add_job(
        send_private_zulip_reminder,
        "date",
        run_date=request.deadline,
        args=[last_record_id, to],
        id=str(last_record_id)
    )
    return {"success": True, "reminder_id": last_record_id}


@app.post("/timezone", response_class=JSONResponse)
async def set_timezone(request: dict = Body(...)):
    check = "SELECT * FROM timezone WHERE email = :email"
    user = await database.fetch_one(
        check, values={"email": request["email"]}
    )
    if user:
        query = timezone.update().values(
            email=request["email"],
            zone=request["timezone"]
        )
    else:
        query = timezone.insert().values(
            email=request["email"],
            zone=request["timezone"]
        )
    await database.execute(query)
    return {"success": True}


async def get_timezone(email):
    query = "SELECT zone FROM timezone WHERE email = :email"
    zone = await database.fetch_one(query=query, values={"email": email})
    if not zone:
        return
    return app.current_timezone - datetime.datetime.now(pytz.timezone(zone[0])).utcoffset()


async def get_time(date):
    hour, minute, unit, value, day = None, None, None, None, None
    for i in date:
        if ":" in i:
            hour, minute = i.split(":")
        if ARGS_WEEK_DAY.get(i) is not None:
            day = ARGS_WEEK_DAY[i]
        if i in ARGS_INTERVAL:
            unit = i if i.endswith("s") else i + "s"
        if i.isdigit():
            value = int(i)
    return hour, minute, unit, value, day


async def get_user(full_name):
    members = client.get_members()['members']
    for user in members:
        if full_name == user["full_name"]:
            return user["email"]
