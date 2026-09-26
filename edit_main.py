import sys
import re

with open('services/api-gateway/app/main.py', 'r') as f:
    content = f.read()

# Add endpoints
endpoints = '''

@app.get("/api/v1/budget")
async def get_budget():
    from .db import get_provider_usage_today
    usage = get_provider_usage_today()
    return {"usage": usage}

@app.get("/api/v1/templates")
async def get_templates():
    from .db import get_templates as db_get_templates
    templates = db_get_templates()
    return {"templates": templates}
'''
content = content + endpoints

with open('services/api-gateway/app/main.py', 'w') as f:
    f.write(content)
