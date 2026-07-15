# 5.5 DevSecOps & Security Automation
Shift-left security pipeline (GitHub Actions)

### Code Pattern
```yaml
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: SAST Semgrep
        uses: semgrep/semgrep-action@v1
```