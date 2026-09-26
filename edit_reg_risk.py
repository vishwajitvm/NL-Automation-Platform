import sys
import re

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

# find the end of REGISTRY dict
# It's a dict that ends with browser_clear_managed_cache
additions = '''
    "send_slack_webhook": (SlackWebhookParams, send_slack_webhook),
    "send_discord_webhook": (DiscordWebhookParams, send_discord_webhook),
    "create_calendar_event": (CreateCalendarEventParams, create_calendar_event),
    "append_google_sheet_row": (AppendSheetRowParams, append_google_sheet_row),
    "send_sms": (SendSMSParams, send_sms),
    "list_running_applications": (EmptyParams, list_running_applications),
'''

content = re.sub(r'("browser_clear_managed_cache": \([^)]+\),)', r'\1\n' + additions, content)

with open('services/execution-sandbox/app/registry.py', 'w') as f:
    f.write(content)

# For risk.py
with open('services/execution-sandbox/app/risk.py', 'r') as f:
    content = f.read()

risk_additions = '''
    "send_slack_webhook": "low",
    "send_discord_webhook": "low",
    "create_calendar_event": "low",
    "append_google_sheet_row": "low",
    "send_sms": "low",
    "list_running_applications": "low",
'''
content = re.sub(r'("browser_clear_managed_cache": "medium",)', r'\1\n' + risk_additions, content)

with open('services/execution-sandbox/app/risk.py', 'w') as f:
    f.write(content)
