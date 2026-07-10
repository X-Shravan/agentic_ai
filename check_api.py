#!/usr/bin/env python3
"""Check API server validation"""

with open('api_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

checks = {
    'Sharing type tracking': '"Sharing Answers" in situation' in content,
    'Emoji detection': '"🚨" in situation or "🤝" in situation' in content,
    'Display frame usage': 'save_screenshot(' in content,
}

for check_name, result in checks.items():
    status = '✅' if result else '❌'
    print(f'{status} {check_name}: {result}')
