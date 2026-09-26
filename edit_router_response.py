with open('services/intent-parser/app/router.py', 'r') as f:
    content = f.read()

content = content.replace('target_params: Optional[Dict[str, Any]] = None', '''target_params: Optional[Dict[str, Any]] = None
    needs_clarification: bool = False
    clarifying_question: Optional[str] = None''')

with open('services/intent-parser/app/router.py', 'w') as f:
    f.write(content)
