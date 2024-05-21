
## A bot that schedules reminders for users.

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
```#stream text every week at 15:00 start on Monday end on 2 June```
or you can add reminder for every last or first day of the month
```<to> <some text> every last day of the month``` will be every last day at 9:00 or 
 if you need to set time ```<to> <some text> every last day of the month at 15:00```


To remove a reminder:
```remove <reminder_id>```
``remove 2``

To list reminders:
```list```

## -------------------------------------------------
Based on https://github.com/apkallum/zulip-reminder-bot

### For run bot
`uvicorn app:app`

`zulip-run-bot remindmoi_bot_handler.py --config-file zuliprc`
