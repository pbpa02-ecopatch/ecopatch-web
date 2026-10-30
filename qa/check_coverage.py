"""Fail CI unless both statement and branch coverage are strictly above 90%."""
import json
import sys
from pathlib import Path

report = Path(sys.argv[1] if len(sys.argv) > 1 else 'qa/artifacts/coverage.json')
totals = json.loads(report.read_text())['totals']
line = 100 * totals['covered_lines'] / totals['num_statements']
branch = 100 * totals['covered_branches'] / totals['num_branches'] if totals['num_branches'] else 100
print(f'Statement coverage: {line:.2f}%')
print(f'Branch coverage: {branch:.2f}%')
if min(line, branch) <= 90:
    raise SystemExit('Both coverage metrics must be strictly above 90%.')
