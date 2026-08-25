from pathlib import Path
spec_path = Path('_bmad-output/implementation-artifacts/8-3-income-voice-and-text-logging-orchestrator.md')
text = spec_path.read_text(encoding='utf-8')
# Check off all [Review][Patch] and [Review][Decision]
text = text.replace('- [ ] [Review][Decision]', '- [x] [Review][Decision]')
text = text.replace('- [ ] [Review][Patch]', '- [x] [Review][Patch]')
spec_path.write_text(text, encoding='utf-8')
print("Checked off")
