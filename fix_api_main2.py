with open('services/api-gateway/app/main.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for l in lines:
    if 'return {' in l and 'id' in lines[lines.index(l) + 1] and 'decision_data' in lines[lines.index(l) + 1]:
        new_lines.append('            if decision_data.get("risk_tier") and plan_data.get("action"):\n')
        new_lines.append('                plan_data["action"]["risk_tier"] = decision_data.get("risk_tier")\n')
    
    new_lines.append(l)

with open('services/api-gateway/app/main.py', 'w') as f:
    f.writelines(new_lines)
