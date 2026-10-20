"""Interactive local email setup; credentials remain in backend/.env."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'backend/.env'
print('Configure the verified Resend sender. Patients and doctors can register with any valid email.')
sender = input('Verified sender (e.g. Preconsultation <hello@your-domain.com>): ').strip()
if '\n' in sender or '\r' in sender or '@' not in sender:
    raise SystemExit('Enter a valid sender address.')
updates = {'RESEND_FROM_EMAIL': sender}
lines = path.read_text().splitlines() if path.exists() else []
output = []
for line in lines:
    key = line.split('=', 1)[0]
    if key in updates:
        output.append(key + '=' + updates.pop(key))
    else:
        output.append(line)
output.extend(key + '=' + value for key, value in updates.items())
path.write_text('\n'.join(output) + '\n')
path.chmod(0o600)
print('Saved. Restart with scripts/stop-local.sh then scripts/start-local.sh.')
