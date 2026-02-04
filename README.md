# 🏥 Multi-Clinic SaaS Platform

A comprehensive, high-performance **Multi-Clinic Management System** with AI-powered automation, advanced billing, and subscription management.

## 🌟 Key Features

### 1. **Multi-Clinic SaaS Architecture** 
- Complete tenant isolation
- Subscription-based access control
- Role-based permissions (Super Admin, Clinic Admin, Doctor, Receptionist, Staff)
- Clinic-wise branding and configurations
- Scalable architecture for multiple clinics

### 2. **Advanced Billing & Revenue Management**
- Service-based billing with line items
- Automated invoice generation
- Tax calculations
- Discount management (percentage & amount-based)
- Partial and advance payments
- Revenue reports and analytics
- Multiple payment methods support
- Overdue invoice tracking

### 3. **AI-Powered Automation**
- Intelligent chatbot for patient inquiries
- Automated lead capture and management
- Intent detection (appointment, inquiry, emergency, complaint)
- Entity extraction (phone, email, dates)
- Lead-to-patient conversion
- Conversation history tracking
- Multi-platform support (WhatsApp, Instagram, Facebook, Website)
- Automated follow-up scheduling

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- UV (Python package manager)

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd clinic-saas
```

2. **Install UV** (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. **Create virtual environment and install dependencies**
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize database**
```bash
# The database will be automatically initialized on first run
# Or manually run:
python -c "from database import init_db; init_db()"
```

6. **Run the application**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

7. **Create demo data** (optional)
```bash
curl -X POST http://localhost:8000/demo/setup
```

## 📚 API Documentation

Once running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Core Endpoints

#### Authentication
- `POST /api/auth/login` - Login and get JWT token
- `POST /api/auth/register` - Register new user
- `GET /api/auth/me` - Get current user info

#### Multi-Clinic Management
- `POST /api/clinics/` - Create new clinic
- `GET /api/clinics/{clinic_id}` - Get clinic details
- `GET /api/clinics/{clinic_id}/stats` - Get clinic statistics
- `POST /api/clinics/{clinic_id}/upgrade` - Upgrade subscription
- `GET /api/clinics/{clinic_id}/limits/{limit_type}` - Check subscription limits

#### Billing & Invoicing
- `POST /api/billing/{clinic_id}/services` - Create service
- `GET /api/billing/{clinic_id}/services` - List services
- `POST /api/billing/{clinic_id}/invoices` - Create invoice
- `GET /api/billing/{clinic_id}/invoices` - List invoices
- `POST /api/billing/{clinic_id}/payments` - Record payment
- `GET /api/billing/{clinic_id}/reports/revenue` - Get revenue report

#### AI Automation
- `POST /api/ai/{clinic_id}/chatbot` - Chatbot interaction (public)
- `POST /api/ai/{clinic_id}/leads` - Create lead manually
- `GET /api/ai/{clinic_id}/leads` - List leads
- `POST /api/ai/{clinic_id}/leads/{lead_id}/convert` - Convert lead to patient
- `GET /api/ai/{clinic_id}/stats` - Get AI statistics

## 🏗️ Architecture

### Database Models

```
┌─────────────┐
│   Clinic    │ (Multi-tenant root)
├─────────────┤
│ - id        │
│ - code      │
│ - features  │
│ - ai_config │
└─────────────┘
      │
      ├──── Users (with roles)
      ├──── Patients
      ├──── Appointments
      ├──── Invoices
      │       └──── Payments
      ├──── Services
      └──── Leads
              └──── AI Interactions
```

### Tech Stack
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT with role-based access
- **Package Manager**: UV
- **Server**: Uvicorn with async support

## 🔐 Security Features

- JWT-based authentication
- Password hashing with bcrypt
- Role-based access control (RBAC)
- Tenant isolation at database level
- Subscription status validation
- Rate limiting ready
- CORS configuration

## 📊 Subscription Tiers

### Free Tier
- 2 doctors max
- 50 patients max
- Basic features only

### Basic Tier
- 5 doctors max
- 200 patients max
- Advanced billing
- Basic analytics

### Premium Tier
- 15 doctors max
- 1000 patients max
- AI automation
- Advanced analytics
- Multi-platform integration

### Enterprise Tier
- Unlimited doctors & patients
- All features
- WhatsApp Business API
- Priority support

## 🤖 AI Features Details

### Intent Detection
The system automatically detects user intent:
- **Appointment**: Booking requests
- **Inquiry**: General questions
- **Emergency**: Urgent care needs
- **Complaint**: Issues or concerns
- **Greeting**: Initial contact

### Entity Extraction
Automatically extracts:
- Phone numbers
- Email addresses
- Date mentions
- Name information

### Lead Management Workflow
```
New Lead → AI Interaction → Qualification → Conversion → Patient
     ↓            ↓              ↓              ↓
   Status:     Intent      Follow-up      Medical
   NEW      Detection     Scheduling      Records
```

## 📈 Performance Optimization

- Connection pooling (20 base, 40 max overflow)
- Database query optimization with indexes
- GZip compression for responses
- Async/await throughout
- Proper transaction management
- Response caching ready

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## 📝 Environment Variables

Key environment variables (see `.env.example`):

```bash
DATABASE_URL=postgresql://user:pass@localhost/clinic_saas
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ALLOWED_ORIGINS=http://localhost:3000
```

## 🚦 API Response Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden (subscription/permission)
- `404` - Not Found
- `500` - Internal Server Error

## 🔄 Development Workflow

1. Make changes to code
2. Run with `--reload` for auto-restart
3. Test endpoints via Swagger UI
4. Check logs for debugging
5. Commit changes

## 📦 Project Structure

```
ANOSIUM-BE/
│
├── main.py
├── core/
│   ├── config.py
│   ├── security.py
│   ├── database.py
│   ├── tenant.py
│
├── models/
│   ├── base.py
│   ├── clinic.py
│   ├── user.py
│   ├── patient.py
│   ├── doctor.py
│   ├── appointment.py
│   ├── service.py
│   ├── invoice.py
│
├── schemas/
│   ├── auth.py
│   ├── clinic.py
│   ├── patient.py
│   ├── doctor.py
│   ├── appointment.py
│   ├── invoice.py
│
├── api/
│   ├── deps.py
│   ├── auth.py
│   ├── clinics.py
│   ├── patients.py
│   ├── doctors.py
│   ├── appointments.py
│   ├── billing.py
│
├── services/
│   ├── auth_service.py
│   ├── billing_service.py
│   ├── ai_demo_service.py
│
├── middlewares/
│   ├── tenant_middleware.py
│
└── utils/
    ├── hashing.py
    ├── response.py
```

## 🎯 Demo Credentials

After running `/demo/setup`:

**Admin User:**
- Username: `admin`
- Password: `admin123`

**Doctor User:**
- Username: `doctor1`
- Password: `doctor123`

## 🔮 Future Enhancements

- [ ] WhatsApp Business API integration
- [ ] Email notifications
- [ ] SMS reminders
- [ ] Payment gateway integration
- [ ] Advanced analytics dashboard
- [ ] Mobile app
- [ ] Telemedicine features
- [ ] Electronic health records (EHR)
- [ ] Prescription management
- [ ] Lab integration

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📄 License

This project is proprietary software. All rights reserved.

## 📞 Support

For support, email support@anosuim.com or open an issue.

---

Built with ❤️ using FastAPI and modern Python by @Bridge Homies
https://app.coderabbit.ai/login???free-trial
