"""
Diagnostic script to identify Pydantic model rebuild issues
Run this BEFORE starting your FastAPI app
"""

import sys
import traceback
from pathlib import Path

print("=" * 80)
print("PYDANTIC MODEL DIAGNOSTIC TOOL")
print("=" * 80)

# Test 1: Import schemas module
print("\n📦 Test 1: Importing schemas module...")
try:
    import schemas
    print("✅ schemas module imported successfully")
except Exception as e:
    print(f"❌ Failed to import schemas: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 2: Import Doctor model specifically
print("\n👨‍⚕️ Test 2: Importing Doctor model...")
try:
    from schemas.doctor import Doctor
    print(f"✅ Doctor model imported: {Doctor}")
    print(f"   Fields: {list(Doctor.model_fields.keys())}")
except Exception as e:
    print(f"❌ Failed to import Doctor: {e}")
    traceback.print_exc()

# Test 3: Check for forward references
print("\n🔍 Test 3: Checking Doctor model for forward references...")
try:
    from schemas.doctor import Doctor
    for field_name, field_info in Doctor.model_fields.items():
        annotation = field_info.annotation
        print(f"   {field_name}: {annotation}")
        
        # Check if it's a string (forward reference)
        if isinstance(annotation, str):
            print(f"   ⚠️  WARNING: {field_name} uses string forward reference: {annotation}")
except Exception as e:
    print(f"❌ Failed to check fields: {e}")
    traceback.print_exc()

# Test 4: Rebuild all models
print("\n🔧 Test 4: Rebuilding all models...")
try:
    from schemas import rebuild_all_models
    rebuild_all_models()
    print("✅ All models rebuilt successfully")
except Exception as e:
    print(f"❌ Failed to rebuild models: {e}")
    traceback.print_exc()

# Test 5: Test Doctor model after rebuild
print("\n✨ Test 5: Testing Doctor model after rebuild...")
try:
    from schemas.doctor import Doctor
    
    # Try to create model schema
    schema = Doctor.model_json_schema()
    print("✅ Doctor JSON schema generated successfully")
    print(f"   Schema has {len(schema.get('properties', {}))} properties")
    
    # Check for $ref in schema (indicates forward references)
    if '$defs' in schema:
        print(f"   📋 Schema has {len(schema['$defs'])} definitions")
        for def_name in schema['$defs'].keys():
            print(f"      - {def_name}")
    
except Exception as e:
    print(f"❌ Failed to generate Doctor schema: {e}")
    traceback.print_exc()

# Test 6: Test FastAPI with Doctor
print("\n🚀 Test 6: Testing FastAPI compatibility...")
try:
    from fastapi import FastAPI
    from schemas.doctor import Doctor
    
    app = FastAPI()
    
    @app.get("/test", response_model=Doctor)
    async def test_endpoint():
        return {}
    
    # Try to generate OpenAPI schema
    openapi_schema = app.openapi()
    print("✅ FastAPI OpenAPI schema generated successfully")
    print(f"   Paths: {list(openapi_schema.get('paths', {}).keys())}")
    
except Exception as e:
    print(f"❌ Failed FastAPI test: {e}")
    traceback.print_exc()

# Test 7: Check for circular imports
print("\n🔄 Test 7: Checking for circular import issues...")
try:
    import_order = [
        "schemas.tenant",
        "schemas.user", 
        "schemas.department",
        "schemas.doctor",
        "schemas.patient",
        "schemas.appointment",
    ]
    
    for module_name in import_order:
        try:
            __import__(module_name)
            print(f"   ✅ {module_name}")
        except Exception as e:
            print(f"   ❌ {module_name}: {e}")
            
except Exception as e:
    print(f"❌ Circular import test failed: {e}")
    traceback.print_exc()

# Test 8: Check endpoint imports
print("\n📡 Test 8: Testing endpoint imports...")
try:
    from api.v1.endpoints.doctors import router
    print("✅ Doctors router imported successfully")
    print(f"   Routes: {[route.path for route in router.routes]}")
except Exception as e:
    print(f"❌ Failed to import doctors router: {e}")
    traceback.print_exc()

# Summary
print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
print("\n📋 Next steps:")
print("1. If any test failed, fix that issue first")
print("2. If Test 3 shows forward references, ensure they use string annotations")
print("3. If Test 5 failed, check your Doctor model definition")
print("4. If Test 6 failed, the issue is in how FastAPI processes the schema")
print("5. If Test 8 failed, check your endpoint type annotations")
print("\n💡 Common fixes:")
print("   - Use TYPE_CHECKING and string annotations for circular refs")
print("   - Call model_rebuild() AFTER all models are imported")
print("   - Avoid using model types in Annotated dependencies")
print("=" * 80)