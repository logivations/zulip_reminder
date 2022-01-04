
## A bot that schedules reminders for users.

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

`add to <@user_name> about <text> at <date>`

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


Based on https://github.com/apkallum/zulip-reminder-bot

### For run bot
`uvicorn app:app`

`zulip-run-bot remindmoi_bot_handler.py --config-file zuliprc`