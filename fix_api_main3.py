with open('services/api-gateway/app/main.py', 'r') as f:
    content = f.read()

content = content.replace(
'''        if decision_data.get("status") == "draft":
            logger.info(f"Automation paused in draft: prompt='{decision_data.get('clarification_question')}'")
            return {
                "id": decision_data["automation_id"],''',
'''        if decision_data.get("status") == "draft":
            logger.info(f"Automation paused in draft: prompt='{decision_data.get('clarification_question')}'")
            if decision_data.get("risk_tier") and plan_data.get("action"):
                plan_data["action"]["risk_tier"] = decision_data.get("risk_tier")
            return {
                "id": decision_data["automation_id"],
                "degraded_mode": plan_data.get("degraded_mode", False),'''
)

content = content.replace(
'''        if decision_data.get("status") == "draft":
            return {
                "id": decision_data["automation_id"],''',
'''        if decision_data.get("status") == "draft":
            if decision_data.get("risk_tier") and plan_data.get("action"):
                plan_data["action"]["risk_tier"] = decision_data.get("risk_tier")
            return {
                "id": decision_data["automation_id"],
                "degraded_mode": plan_data.get("degraded_mode", False),'''
)

with open('services/api-gateway/app/main.py', 'w') as f:
    f.write(content)
