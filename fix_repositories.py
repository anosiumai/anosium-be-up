# fix_repositories.py
import re
from pathlib import Path

# List of files to fix
files_to_fix = [
    "repositories/ai_lead.py",
    "repositories/analytics.py",
    "repositories/appointment.py",
    "repositories/audit.py",
    "repositories/billing.py",
    "repositories/department.py",
    "repositories/doctor.py",
    "repositories/notification.py",
    "repositories/service.py",
    "repositories/visit.py",
]

def fix_init_call(content):
    """Fix super().__init__(Model, db, ...) → super().__init__(db, Model, ...)"""
    pattern = r'super\(\).__init__\((\w+),\s*(db),'
    replacement = r'super().__init__(\2, \1,'
    return re.sub(pattern, replacement, content)

for filepath in files_to_fix:
    path = Path(filepath)
    if path.exists():
        content = path.read_text()
        new_content = fix_init_call(content)
        
        if new_content != content:
            path.write_text(new_content)
            print(f"✅ Fixed: {filepath}")
        else:
            print(f"⚠️  No changes: {filepath}")
    else:
        print(f"❌ Not found: {filepath}")

print("\n✅ All repositories fixed! Restart the server.")