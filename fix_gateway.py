with open('services/api-gateway/app/main.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for l in lines:
    if l.startswith('                return {') and 'needs_clarification' in new_lines[-1]:
        new_lines.append('                    return {\n')
    elif l.startswith('                    "id": "temp-disambiguate",') and 'needs_clarification' in new_lines[-3]:
        new_lines.append('                        "id": "temp-disambiguate",\n')
    elif l.startswith('                    "status": "blocked",') and 'needs_clarification' in new_lines[-4]:
        new_lines.append('                        "status": "blocked",\n')
    elif l.startswith('                    "clarification_prompt": route_data.get("clarifying_question"),') and 'needs_clarification' in new_lines[-5]:
        new_lines.append('                        "clarification_prompt": route_data.get("clarifying_question"),\n')
    elif l.startswith('                    "plan": None') and 'needs_clarification' in new_lines[-6]:
        new_lines.append('                        "plan": None\n')
    elif l.startswith('                }') and 'needs_clarification' in new_lines[-7]:
        new_lines.append('                    }\n')
    else:
        new_lines.append(l)

with open('services/api-gateway/app/main.py', 'w') as f:
    f.writelines(new_lines)
