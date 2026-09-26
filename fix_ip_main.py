import re
with open('services/intent-parser/app/main.py', 'r') as f:
    content = f.read()

# When we create AutomationPlan at the bottom:
content = content.replace(
    '''    plan = AutomationPlan(
        raw_text=raw_text,
        trigger=parsed.trigger,
        action=parsed.action,
        ambiguities=parsed.ambiguities,
        parseable=True
    )''',
    '''    plan = AutomationPlan(
        raw_text=raw_text,
        trigger=parsed.trigger,
        action=parsed.action,
        ambiguities=parsed.ambiguities,
        parseable=True,
        degraded_mode=parsed.degraded_mode
    )'''
)

# And in the parsed audit log:
content = content.replace(
    '''log_audit_event("parsed", {
        "action": action_name,
        "trigger": trigger_type,
        "raw_text": raw_text
    })''',
    '''log_audit_event("parsed", {
        "action": action_name,
        "trigger": trigger_type,
        "raw_text": raw_text,
        "degraded_mode": parsed.degraded_mode
    })'''
)

with open('services/intent-parser/app/main.py', 'w') as f:
    f.write(content)
