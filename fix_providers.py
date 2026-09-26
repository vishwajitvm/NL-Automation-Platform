import re

with open('services/intent-parser/app/providers.py', 'r') as f:
    content = f.read()

# Add degraded_mode to ParsedResult
content = content.replace(
    "ambiguities: List[Ambiguity] = Field(default_factory=list)",
    "ambiguities: List[Ambiguity] = Field(default_factory=list)\n    degraded_mode: bool = False"
)

# In DeterministicRuleProvider, add degraded_mode=True to all ParsedResult initializations
# DeterministicRuleProvider starts with class DeterministicRuleProvider
idx = content.find('class DeterministicRuleProvider(LLMProvider):')
prefix = content[:idx]
suffix = content[idx:]

# replace all ParsedResult( in suffix with setting degraded_mode=True
# Actually, it's easier to just append degraded_mode=True before the closing bracket of ParsedResult
suffix = re.sub(r'(ParsedResult\([^)]+)(ambiguities=[^\n]+)(\n\s*\))', r'\1\2,\n            degraded_mode=True\3', suffix, flags=re.DOTALL)

with open('services/intent-parser/app/providers.py', 'w') as f:
    f.write(prefix + suffix)
