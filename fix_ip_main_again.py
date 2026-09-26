with open('services/intent-parser/app/main.py', 'r') as f:
    content = f.read()

content = content.replace(
'''    # 3. Successful parse
    return AutomationPlan(
        raw_text=raw_text,
        trigger=parsed.trigger,
        action=parsed.action,
        ambiguities=parsed.ambiguities,
        parseable=True
    )''',
'''    # 3. Successful parse
    from .db import log_audit_event
    log_audit_event("parsed", {
        "action": action_name,
        "trigger": trigger_type,
        "raw_text": raw_text,
        "degraded_mode": parsed.degraded_mode
    })
    return AutomationPlan(
        raw_text=raw_text,
        trigger=parsed.trigger,
        action=parsed.action,
        ambiguities=parsed.ambiguities,
        parseable=True,
        degraded_mode=parsed.degraded_mode
    )'''
)

with open('services/intent-parser/app/main.py', 'w') as f:
    f.write(content)
