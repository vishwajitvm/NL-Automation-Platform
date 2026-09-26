import re

with open('services/api-gateway/app/main.py', 'r') as f:
    content = f.read()

# 1. Fix route_data.get("needs_clarification") in create_automation (approx line 150)
content = re.sub(
    r'if route_data\.get\("needs_clarification"\):\n\s+return \{\n\s+"id": "temp-disambiguate",\n\s+"status": "blocked",\n\s+"clarification_prompt": route_data\.get\("clarifying_question"\),\n\s+"plan": None\n\s+\}',
    r'''if route_data.get("needs_clarification"):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "GUARDRAIL_BLOCKED",
                        "message": f"Ambiguous request: {route_data.get('clarifying_question')}"
                    }
                )''',
    content
)

# 2. Fix route_data.get("needs_clarification") in commands (approx line 230)
content = re.sub(
    r'if route_data\.get\("needs_clarification"\):\n\s+return \{\n\s+"id": "temp-disambiguate",\n\s+"status": "blocked",\n\s+"clarification_prompt": route_data\.get\("clarifying_question"\),\n\s+"plan": None\n\s+\}',
    r'''if route_data.get("needs_clarification"):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "GUARDRAIL_BLOCKED",
                        "message": f"Ambiguous request: {route_data.get('clarifying_question')}"
                    }
                )''',
    content
)

# 3. Fix ethics_data.get("verdict") == "needs_clarification" in handle_informational_query
content = re.sub(
    r'if ethics_data\.get\("verdict"\) == "needs_clarification":\n\s+return \{\n\s+"id": str\(uuid\.uuid4\(\)\),\n\s+"status": "draft",\n\s+"lane": "informational_query",\n\s+"clarification_prompt": ethics_data\.get\("clarifying_question", "Could you clarify the purpose of this request\?"\),\n\s+"reasoning": ethics_data\.get\("reasoning"\),\n\s+\}',
    r'''if ethics_data.get("verdict") == "needs_clarification":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "GUARDRAIL_BLOCKED",
                "message": f"Ethics review requires clarification: {ethics_data.get('clarifying_question', 'Could you clarify the purpose of this request?')}",
                "reasoning": ethics_data.get("reasoning")
            }
        )''',
    content
)


with open('services/api-gateway/app/main.py', 'w') as f:
    f.write(content)
