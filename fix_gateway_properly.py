with open('services/api-gateway/app/main.py', 'r') as f:
    content = f.read()

import re
content = re.sub(
r'''                if route_data\.get\("needs_clarification"\):
                    return \{
                    "id": "temp-disambiguate",
                    "status": "blocked",
                    "clarification_prompt": route_data\.get\("clarifying_question"\),
                    "plan": None
                \}''', 
r'''                if route_data.get("needs_clarification"):
                    return {
                        "id": "temp-disambiguate",
                        "status": "blocked",
                        "clarification_prompt": route_data.get("clarifying_question"),
                        "plan": None
                    }''', content)

content = re.sub(
r'''            if route_data\.get\("needs_clarification"\):
                    return \{
                    "id": "temp-disambiguate",
                    "status": "blocked",
                    "clarification_prompt": route_data\.get\("clarifying_question"\),
                    "plan": None
                \}''',
r'''            if route_data.get("needs_clarification"):
                return {
                    "id": "temp-disambiguate",
                    "status": "blocked",
                    "clarification_prompt": route_data.get("clarifying_question"),
                    "plan": None
                }''', content)

with open('services/api-gateway/app/main.py', 'w') as f:
    f.write(content)
