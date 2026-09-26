import re

with open('services/intent-parser/app/providers.py', 'r') as f:
    content = f.read()

# For any ParsedResult inside DeterministicRuleProvider, add degraded_mode=True
# First, revert any previous degraded_mode=True in ParsedResult
content = re.sub(r',\s*degraded_mode=True\s*\)', '\n            )', content)

# Then properly add it to all ParsedResult instantiations that belong to DeterministicRuleProvider
# We can just replace mbiguities=[] with mbiguities=[], degraded_mode=True 
# and mbiguities=[\n\s*Ambiguity(...)\n\s*] with ..., degraded_mode=True
# Wait, let's just do a simple replacement for mbiguities=[] -> mbiguities=[], degraded_mode=True
# and ]\n                ) -> ],\n                    degraded_mode=True\n                )

content = re.sub(r'ambiguities=\[\]\s*\n\s*\)', r'ambiguities=[], degraded_mode=True)', content)
content = re.sub(r'(\s*\])\s*\n\s*\)', r'\1,\n                        degraded_mode=True\n                    )', content)


with open('services/intent-parser/app/providers.py', 'w') as f:
    f.write(content)
