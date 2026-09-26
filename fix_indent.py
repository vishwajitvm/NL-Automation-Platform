with open('services/api-gateway/app/main.py', 'r') as f:
    content = f.read()

content = content.replace(
'''                if route_data.get("needs_clarification"):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "GUARDRAIL_BLOCKED",
                        "message": f"Ambiguous request: {route_data.get('clarifying_question')}"
                    }
                )''',
'''                if route_data.get("needs_clarification"):
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "GUARDRAIL_BLOCKED",
                            "message": f"Ambiguous request: {route_data.get('clarifying_question')}"
                        }
                    )'''
)

with open('services/api-gateway/app/main.py', 'w') as f:
    f.write(content)
