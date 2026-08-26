import re
from datetime import datetime

def update_sprint():
    with open('_bmad-output/implementation-artifacts/sprint-status.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'7-2-quota-gating-and-upgrade-prompt: review', '7-2-quota-gating-and-upgrade-prompt: done', content)
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    content = re.sub(r'last_updated: .*', f'last_updated: {current_time}', content)

    with open('_bmad-output/implementation-artifacts/sprint-status.yaml', 'w', encoding='utf-8') as f:
        f.write(content)

update_sprint()
