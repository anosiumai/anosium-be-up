"""
Auto-fix schemas/__init__.py by detecting what's actually available
"""

import ast
import os
from pathlib import Path

print("=" * 80)
print("AUTO-FIX SCHEMAS/__init__.py")
print("=" * 80)

schemas_dir = Path("schemas")

def get_exports_from_file(filepath):
    """Extract all class names from a Python file"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
        
        return classes
    except Exception as e:
        print(f"⚠️  Error reading {filepath}: {e}")
        return []

# Detect what's available in each file
modules = {
    'tenant': get_exports_from_file(schemas_dir / 'tenant.py'),
    'user': get_exports_from_file(schemas_dir / 'user.py'),
    'patient': get_exports_from_file(schemas_dir / 'patient.py'),
    'department': get_exports_from_file(schemas_dir / 'department.py'),
    'doctor': get_exports_from_file(schemas_dir / 'doctor.py'),
    'service': get_exports_from_file(schemas_dir / 'service.py'),
    'appointment': get_exports_from_file(schemas_dir / 'appointment.py'),
    'visit': get_exports_from_file(schemas_dir / 'visit.py'),
    'billing': get_exports_from_file(schemas_dir / 'billing.py'),
    'ai_lead': get_exports_from_file(schemas_dir / 'ai_lead.py'),
    'notification': get_exports_from_file(schemas_dir / 'notification.py'),
}

print("\n📦 Detected exports from each module:")
print("-" * 80)
for module, classes in modules.items():
    print(f"\n{module}:")
    if classes:
        for cls in classes:
            print(f"   - {cls}")
    else:
        print("   (empty or error)")

# Generate the corrected __init__.py
print("\n" + "=" * 80)
print("GENERATING CORRECTED __init__.py")
print("=" * 80)

init_content = '''"""
Schemas Package - Pydantic Models
Auto-generated with correct imports based on actual file contents
"""

# ============================================================================
# TIER 1: Base models with NO dependencies on other schemas
# ============================================================================

'''

# Tier 1 imports
for module in ['tenant', 'user', 'patient']:
    if modules[module]:
        init_content += f"from .{module} import {', '.join(modules[module])}\n"

init_content += '''
# Utility modules
try:
    from .common import *
except ImportError:
    pass

try:
    from .auth import *
except ImportError:
    pass

# ============================================================================
# TIER 2: Models with CIRCULAR dependencies (department ↔ doctor)
# ============================================================================

'''

# Tier 2 imports
for module in ['department', 'doctor']:
    if modules[module]:
        init_content += f"from .{module} import {', '.join(modules[module])}\n"

init_content += '''

# ============================================================================
# TIER 3: Models that depend on Tier 1 & 2
# ============================================================================

'''

# Tier 3 imports
for module in ['service', 'appointment', 'visit', 'billing', 'ai_lead', 'notification']:
    if modules[module]:
        init_content += f"from .{module} import {', '.join(modules[module])}\n"

init_content += '''

# ============================================================================
# REBUILD FUNCTION
# ============================================================================

def rebuild_all_models():
    """Rebuild all Pydantic models to resolve forward references."""
    
    import sys
    current_module = sys.modules[__name__]
    
    # Collect all model classes from current module
    models = []
    for name in dir(current_module):
        obj = getattr(current_module, name)
        if isinstance(obj, type) and hasattr(obj, 'model_rebuild'):
            models.append(obj)
    
    print(f"\\n🔧 Rebuilding {len(models)} Pydantic models...")
    print("=" * 70)
    
    failed = []
    for model in models:
        try:
            model.model_rebuild()
            print(f"   ✅ {model.__name__}")
        except Exception as e:
            failed.append((model.__name__, str(e)))
            print(f"   ⚠️  {model.__name__}: {str(e)[:60]}")
    
    print("=" * 70)
    if failed:
        print(f"⚠️  {len(failed)} model(s) failed to rebuild")
    else:
        print(f"✅ All {len(models)} models rebuilt successfully!")
    print("=" * 70 + "\\n")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['rebuild_all_models']

# Add all classes to __all__
'''

for module, classes in modules.items():
    for cls in classes:
        init_content += f"__all__.append('{cls}')\n"

# Write to file
output_file = 'schemas_init_auto.py'
with open(output_file, 'w') as f:
    f.write(init_content)

print(f"\n✅ Generated: {output_file}")
print("\n📋 To use this file:")
print("   1. Review it: cat schemas_init_auto.py")
print("   2. Backup current: cp schemas/__init__.py schemas/__init__.py.backup")
print("   3. Replace: cp schemas_init_auto.py schemas/__init__.py")
print("   4. Test: uv run diagnose_pydantic.py")
print("\n" + "=" * 80)