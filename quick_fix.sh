#!/bin/bash

echo "=============================================================================="
echo "QUICK FIX FOR schemas/__init__.py"
echo "=============================================================================="

# Step 1: Check what's in billing.py
echo -e "\n📋 Step 1: Inspecting billing.py..."
python3 inspect_billing.py

# Step 2: Auto-generate corrected __init__.py
echo -e "\n🔧 Step 2: Generating corrected __init__.py..."
python3 auto_fix_init.py

# Step 3: Show what was generated
echo -e "\n📄 Step 3: Preview (first 50 lines)..."
head -50 schemas_init_auto.py

echo -e "\n=============================================================================="
echo "READY TO APPLY"
echo "=============================================================================="
echo "To apply the fix, run:"
echo "  cp schemas/__init__.py schemas/__init__.py.backup"
echo "  cp schemas_init_auto.py schemas/__init__.py"
echo "  uv run diagnose_pydantic.py"
echo "=============================================================================="