import re

def update_status():
    with open('_bmad-output/implementation-artifacts/7-2-quota-gating-and-upgrade-prompt.md', 'r', encoding='utf-8') as f:
        content = f.read()

    # Update frontmatter status
    content = re.sub(r'status: "review"', 'status: "done"', content, count=1)
    # Update Status line
    content = re.sub(r'Status: review', 'Status: done', content, count=1)
    
    # Check off patch findings
    content = content.replace('- [ ] [Review][Decision]', '- [x] [Review][Decision]')
    content = content.replace('- [ ] [Review][Patch]', '- [x] [Review][Patch]')
    
    with open('_bmad-output/implementation-artifacts/7-2-quota-gating-and-upgrade-prompt.md', 'w', encoding='utf-8') as f:
        f.write(content)

update_status()
