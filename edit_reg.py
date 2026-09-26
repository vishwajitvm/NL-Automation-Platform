import sys
with open('services/execution-sandbox/app/registry.py', 'r') as f:
    content = f.read()

imports = '''from .actions.send_slack_webhook import SlackWebhookParams, send_slack_webhook
from .actions.send_discord_webhook import DiscordWebhookParams, send_discord_webhook
from .actions.create_calendar_event import CreateCalendarEventParams, create_calendar_event
from .actions.append_google_sheet_row import AppendSheetRowParams, append_google_sheet_row
from .actions.send_sms import SendSMSParams, send_sms
from .actions.list_running_applications import list_running_applications, EmptyParams
'''

content = imports + content
content = content.replace('}', '''
    "send_slack_webhook": (SlackWebhookParams, send_slack_webhook),
    "send_discord_webhook": (DiscordWebhookParams, send_discord_webhook),
    "create_calendar_event": (CreateCalendarEventParams, create_calendar_event),
    "append_google_sheet_row": (AppendSheetRowParams, append_google_sheet_row),
    "send_sms": (SendSMSParams, send_sms),
    "list_running_applications": (EmptyParams, list_running_applications),
}''')

with open('services/execution-sandbox/app/registry.py', 'w') as f:
    f.write(content)
