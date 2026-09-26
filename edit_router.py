with open('services/intent-parser/app/router.py', 'r') as f:
    content = f.read()

disambiguation = '''
    # Phase 12 disambiguation
    if re.search(r"how many.*tasks.*running|what.*tasks.*running", text_lower):
        return RouteResponse(
            lane="informational_query",
            reason="Ambiguous 'tasks' query",
            needs_clarification=True,
            clarifying_question="Do you mean apps running on your computer, tabs open in your browser, or your own active automations?"
        )
'''

content = content.replace('text_lower = text.lower()', 'text_lower = text.lower()\n' + disambiguation)

with open('services/intent-parser/app/router.py', 'w') as f:
    f.write(content)
