import re
with open('services/api-gateway/app/main.py', 'r') as f:
    content = f.read()

# Fix risk_tier in both /api/v1/automations and /api/v1/commands
content = re.sub(
    r'(logger\.info\(f"Automation paused in draft: prompt=''\{decision_data\.get\(''clarification_question''\)\}''"\)\n\s+)',
    r'\1if decision_data.get("risk_tier") and plan_data.get("action"):\n                plan_data["action"]["risk_tier"] = decision_data.get("risk_tier")\n            ',
    content
)

content = re.sub(
    r'(decision_data = decision_resp\.json\(\)\n\s+if decision_data\.get\("status"\) == "draft":\n\s+)',
    r'\1if decision_data.get("risk_tier") and plan_data.get("action"):\n                plan_data["action"]["risk_tier"] = decision_data.get("risk_tier")\n            ',
    content
)

# Also expose degraded_mode
content = re.sub(
    r'("risk_tier": decision_data\.get\("risk_tier"\),)',
    r'\1\n                "degraded_mode": plan_data.get("degraded_mode", False),',
    content
)

with open('services/api-gateway/app/main.py', 'w') as f:
    f.write(content)
