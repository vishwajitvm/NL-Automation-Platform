import re
with open('services/api-gateway/app/main.py', 'r') as f:
    content = f.read()

# For execute_immediate_command and create_automation
replacement = '''if route_data.get("needs_clarification"):
                return {
                    "id": "temp-disambiguate",
                    "status": "blocked",
                    "clarification_prompt": route_data.get("clarifying_question"),
                    "plan": None
                }
            if route_data.get("lane") == "informational_query":'''

content = re.sub(r'if route_data\.get\("lane"\) == "informational_query":', replacement, content)

with open('services/api-gateway/app/main.py', 'w') as f:
    f.write(content)
