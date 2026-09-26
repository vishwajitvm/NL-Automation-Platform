import re

with open('services/api-gateway/app/main.py', 'r') as f:
    content = f.read()

content = re.sub(
    r'if ethics_data\.get\("verdict"\) == "needs_clarification":\n\s+return \{\n\s+"id": str\(uuid\.uuid4\(\)\),\n\s+"status": "draft",\n\s+"clarification_prompt": ethics_data\.get\("clarifying_question"\),\n\s+"reasoning": ethics_data\.get\("reasoning"\),\n\s+"plan": plan_data\n\s+\}',
    r'''if ethics_data.get("verdict") == "needs_clarification":
            logger.info(f"Ethics review requested clarification: '{ethics_data.get('clarifying_question')}'")
            if not plan_data.get("ambiguities"):
                plan_data["ambiguities"] = [{
                    "field_path": "ethics_clarification",
                    "question": ethics_data.get("clarifying_question", "Could you clarify the purpose of this request?")
                }]''',
    content
)

with open('services/api-gateway/app/main.py', 'w') as f:
    f.write(content)
