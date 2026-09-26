with open('services/execution-sandbox/app/risk.py', 'r') as f:
    content = f.read()

content = content.replace('}', '''
    "send_slack_webhook": "low",
    "send_discord_webhook": "low",
    "create_calendar_event": "low",
    "append_google_sheet_row": "low",
    "send_sms": "low",
    "list_running_applications": "low",
}''')

with open('services/execution-sandbox/app/risk.py', 'w') as f:
    f.write(content)
