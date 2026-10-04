"""Interactive local email setup; credentials remain in backend/.env."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
path = root / 'backend/.env'
print('Configure the verified Resend sender and clinician allowlist.')
sender = input('Verified sender (e.g. Preconsultation <hello@your-domain.com>): ').strip()
doctors = input('Clinician email(s), comma separated: ').strip().lower()
if '\n' in sender or '\r' in sender or '@' not in sender:
    raise SystemExit('Enter a valid sender address.')
if not doctors or any(not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email.strip()) for email in doctors.split(',')):
    raise SystemExit('Enter valid clinician email addresses.')
updates = {'RESEND_FROM_EMAIL': sender, 'DOCTOR_EMAILS': doctors}
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
