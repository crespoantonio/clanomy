from pathlib import Path
import re

# Update story file
spec_path = Path('_bmad-output/implementation-artifacts/8-3-income-voice-and-text-logging-orchestrator.md')
text = spec_path.read_text(encoding='utf-8')
text = re.sub(r'status:\s*"review"', 'status: "done"', text)
text = re.sub(r'Status:\s*review', 'Status: done', text)
spec_path.write_text(text, encoding='utf-8')

# Update sprint status
sprint_path = Path('_bmad-output/implementation-artifacts/sprint-status.yaml')
if sprint_path.exists():
    sprint = sprint_path.read_text(encoding='utf-8')
    sprint = re.sub(r'8-3-income-voice-and-text-logging-orchestrator:\s*review', '8-3-income-voice-and-text-logging-orchestrator: done', sprint)
    from datetime import datetime
    sprint = re.sub(r'last_updated:\s*.*', f'last_updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', sprint)
    sprint_path.write_text(sprint, encoding='utf-8')
print("Status updated")
