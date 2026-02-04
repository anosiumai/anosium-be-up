"""
seed.py — bootstrap demo data so the SignIn demo credentials work out of the box.

Run it once after the database is created:
    python seed.py

It is idempotent: if the tenant or user already exists it just prints a notice
and does nothing.
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import SessionLocal, init_db
from core.security import get_password_hash
from models.tenant import Tenant, SubscriptionTier, SubscriptionStatus
from models.user import User, UserRole


def seed():
    """Seed database with demo data"""
    print("[seed] Starting database seed...")
    
    # 1. Ensure tables exist
    try:
        init_db()
        print("[seed] ✅ Database initialized")
    except Exception as e:
        print(f"[seed] ❌ Error initializing database: {e}")
        raise

    db = SessionLocal()
    try:
        # ── tenant ──────────────────────────────────────────────
        tenant = db.query(Tenant).filter(Tenant.slug == "demo-clinic").first()
        if tenant:
            print("[seed] ℹ️  Tenant 'demo-clinic' already exists — skipping.")
        else:
            tenant = Tenant(
                name="Demo Clinic",
                slug="demo-clinic",
                email="demo@clinic.com",
                phone="+10000000000",
                subscription_tier=SubscriptionTier.FREE,
                subscription_status=SubscriptionStatus.TRIAL,
                enabled_features={
                    "ai_chatbot": False,
                    "advanced_billing": False,
                    "analytics": True,
                    "max_doctors": 2,
                    "max_patients": 50,
                },
                primary_color="#3B82F6",
                settings={},
                is_active=True,
            )
            db.add(tenant)
            db.flush()  # get tenant.id
            print(f"[seed] ✅ Created tenant 'Demo Clinic' (id={tenant.id})")

        # ── admin user ──────────────────────────────────────────
        admin = db.query(User).filter(User.email == "admin@demo-clinic.com").first()
        if admin:
            print("[seed] ℹ️  User 'admin@demo-clinic.com' already exists — skipping.")
        else:
            admin = User(
                tenant_id=tenant.id,
                email="admin@demo-clinic.com",
                hashed_password=get_password_hash("Admin123"),
                first_name="Admin",
                last_name="User",
                role=UserRole.CLINIC_ADMIN,
                is_active=True,
                is_verified=True,
                permissions={},
            )
            db.add(admin)
            print(f"[seed] ✅ Created user 'admin@demo-clinic.com' (role=clinic_admin)")

        db.commit()
        print("\n" + "=" * 60)
        print("🎉 Seed completed successfully!")
        print("=" * 60)
        print("\n📝 Demo Credentials:")
        print(f"   Email:    admin@demo-clinic.com")
        print(f"   Password: Admin123")
        print(f"   Tenant:   Demo Clinic (slug: demo-clinic)")
        print("=" * 60 + "\n")

    except Exception as e:
        db.rollback()
        print(f"[seed] ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()