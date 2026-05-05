"""Add lazy FacebookRegistration import at every call site in auto_reg_mixin.py and login_mixin.py."""
import re

FILES = [
    'src/ui/mixins/auto_reg_mixin.py',
    'src/ui/mixins/login_mixin.py',
    'src/ui/mixins/automation_mixin.py',
]

PATTERN = re.compile(
    r'(?<!from src\.automation\.registration import FacebookRegistration\n)'
    r'(\s+)(registration\s*=\s*FacebookRegistration\()',
)

for path in FILES:
    with open(path, encoding='utf-8') as f:
        content = f.read()

    # Replace every bare `registration = FacebookRegistration(` with a lazy import before it
    new_content = re.sub(
        r'(\n(\s+))(registration\s*=\s*FacebookRegistration\()',
        r'\1from src.automation.registration import FacebookRegistration\n\2\3',
        content,
    )

    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        count = new_content.count('from src.automation.registration import FacebookRegistration')
        print(f'OK {path}: {count} lazy import(s) added')
    else:
        print(f'SKIP {path}: no bare FacebookRegistration() calls found')
