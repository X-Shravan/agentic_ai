#!/usr/bin/env python3
"""Quick API server check"""

with open('api_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check each requirement
sharing_check = 'Sharing Answers' in content and 'in situation' in content
emoji_check = '🚨' in content and '🤝' in content
screenshot_check = 'save_screenshot' in content

print('Sharing Answers tracking:', '✅' if sharing_check else '❌')
print('Emoji detection:', '✅' if emoji_check else '❌')
print('Screenshot function:', '✅' if screenshot_check else '❌')

if sharing_check and emoji_check and screenshot_check:
    print('\n✅ All API server checks pass!')
else:
    print('\n❌ Some checks failing')
