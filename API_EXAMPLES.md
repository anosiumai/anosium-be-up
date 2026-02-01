# API Testing Examples

## Setup Demo Data

```bash
curl -X POST http://localhost:8000/demo/setup
```

## Authentication

### 1. Login (Get JWT Token)
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

Response will include `access_token`. Use this in subsequent requests.

### 2. Get Current User Info
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Multi-Clinic Management

### 1. Create New Clinic (Super Admin only)
```bash
curl -X POST http://localhost:8000/api/clinics/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Advanced Medical Center",
    "email": "info@advancedmedical.com",
    "phone": "+1234567890",
    "address": "456 Healthcare Blvd",
    "subscription_tier": "premium"
  }'
```

### 2. Get Clinic Stats
```bash
curl -X GET http://localhost:8000/api/clinics/{clinic_id}/stats \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Check Subscription Limits
```bash
# Check doctor limit
curl -X GET http://localhost:8000/api/clinics/{clinic_id}/limits/doctors \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Check patient limit
curl -X GET http://localhost:8000/api/clinics/{clinic_id}/limits/patients \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Upgrade Subscription
```bash
curl -X POST http://localhost:8000/api/clinics/{clinic_id}/upgrade \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_tier": "premium",
    "duration_days": 30
  }'
```

## Billing & Invoicing

### 1. Create Service
```bash
curl -X POST http://localhost:8000/api/billing/{clinic_id}/services \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "General Consultation",
    "description": "30-minute consultation with doctor",
    "price": 100.00,
    "tax_percentage": 10.0,
    "category": "consultation"
  }'
```

### 2. List Services
```bash
curl -X GET http://localhost:8000/api/billing/{clinic_id}/services \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Create Invoice
```bash
curl -X POST http://localhost:8000/api/billing/{clinic_id}/invoices \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "line_items": [
      {
        "name": "General Consultation",
        "quantity": 1,
        "price": 100.00,
        "tax_percentage": 10.0
      },
      {
        "name": "Blood Test",
        "quantity": 1,
        "price": 50.00,
        "tax_percentage": 10.0
      }
    ],
    "discount_percentage": 5.0,
    "notes": "Follow-up required in 2 weeks"
  }'
```

### 4. Record Payment
```bash
curl -X POST http://localhost:8000/api/billing/{clinic_id}/payments \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": 1,
    "amount": 100.00,
    "payment_method": "cash",
    "notes": "Paid in full"
  }'
```

### 5. Get Revenue Report
```bash
curl -X GET "http://localhost:8000/api/billing/{clinic_id}/reports/revenue?from_date=2024-01-01&to_date=2024-12-31" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 6. List Pending Invoices
```bash
curl -X GET http://localhost:8000/api/billing/{clinic_id}/invoices/pending/all \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 7. List Overdue Invoices
```bash
curl -X GET http://localhost:8000/api/billing/{clinic_id}/invoices/overdue/all \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## AI Automation

### 1. Chatbot Interaction (Public - No Auth)
```bash
curl -X POST http://localhost:8000/api/ai/{clinic_id}/chatbot \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need to book an appointment",
    "phone": "+1234567890",
    "name": "John Doe",
    "platform": "website"
  }'
```

### 2. WhatsApp Integration
```bash
curl -X POST http://localhost:8000/api/ai/{clinic_id}/chatbot/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, I want to schedule an appointment",
    "phone": "+1234567890",
    "name": "Jane Smith"
  }'
```

### 3. Create Lead Manually
```bash
curl -X POST http://localhost:8000/api/ai/{clinic_id}/leads \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sarah Johnson",
    "phone": "+1987654321",
    "email": "sarah@example.com",
    "source": "referral",
    "initial_message": "Referred by Dr. Smith",
    "intent": "appointment"
  }'
```

### 4. List Leads
```bash
# All leads
curl -X GET http://localhost:8000/api/ai/{clinic_id}/leads \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by status
curl -X GET "http://localhost:8000/api/ai/{clinic_id}/leads?status=new" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by source
curl -X GET "http://localhost:8000/api/ai/{clinic_id}/leads?source=whatsapp" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Update Lead Status
```bash
curl -X PUT http://localhost:8000/api/ai/{clinic_id}/leads/{lead_id}/status \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_status": "qualified",
    "notes": "Interested in general consultation"
  }'
```

### 6. Convert Lead to Patient
```bash
curl -X POST http://localhost:8000/api/ai/{clinic_id}/leads/{lead_id}/convert \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 7. Schedule Follow-up
```bash
curl -X POST http://localhost:8000/api/ai/{clinic_id}/leads/{lead_id}/followup \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "follow_up_date": "2024-02-15T10:00:00Z"
  }'
```

### 8. Get Leads for Follow-up
```bash
curl -X GET http://localhost:8000/api/ai/{clinic_id}/leads/followup/pending \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 9. Get AI Statistics
```bash
curl -X GET "http://localhost:8000/api/ai/{clinic_id}/stats?days=30" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 10. Update AI Configuration
```bash
curl -X POST http://localhost:8000/api/ai/{clinic_id}/config/ai \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "auto_respond": true,
    "lead_capture": true,
    "appointment_booking": false
  }'
```

## User Management

### 1. Create New User
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clinic_id": 1,
    "username": "receptionist1",
    "email": "receptionist1@clinic.com",
    "password": "secure123",
    "full_name": "Mary Johnson",
    "phone": "+1234567892",
    "role": "receptionist"
  }'
```

### 2. List Clinic Users
```bash
# All users
curl -X GET http://localhost:8000/api/auth/{clinic_id}/users \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by role
curl -X GET "http://localhost:8000/api/auth/{clinic_id}/users?role=doctor" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Deactivate User
```bash
curl -X DELETE http://localhost:8000/api/auth/{clinic_id}/users/{user_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Testing Complete Workflow

### Scenario: Lead to Patient Conversion with Invoice

```bash
# Step 1: Lead contacts via chatbot
curl -X POST http://localhost:8000/api/ai/1/chatbot \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need to book an appointment for general checkup",
    "phone": "+1234567890",
    "name": "John Doe"
  }'

# Step 2: Convert lead to patient (as admin)
curl -X POST http://localhost:8000/api/ai/1/leads/1/convert \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Step 3: Create invoice for the patient
curl -X POST http://localhost:8000/api/billing/1/invoices \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "line_items": [
      {
        "name": "General Checkup",
        "quantity": 1,
        "price": 150.00,
        "tax_percentage": 10.0
      }
    ],
    "discount_percentage": 0
  }'

# Step 4: Record payment
curl -X POST http://localhost:8000/api/billing/1/payments \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": 1,
    "amount": 165.00,
    "payment_method": "card"
  }'

# Step 5: Check clinic stats
curl -X GET http://localhost:8000/api/clinics/1/stats \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Health & System Endpoints

```bash
# Health check
curl -X GET http://localhost:8000/health

# System info
curl -X GET http://localhost:8000/info

# Root endpoint
curl -X GET http://localhost:8000/
```

## Tips for Testing

1. **Save the access token**: After login, save the token for subsequent requests
2. **Use variables**: Set clinic_id and token as variables for easier testing
3. **Check response codes**: 200/201 = success, 4xx = client error, 5xx = server error
4. **View detailed docs**: Visit http://localhost:8000/docs for interactive testing
5. **Monitor logs**: Watch the console output for debugging information

## Example Test Script

```bash
#!/bin/bash

# Set variables
BASE_URL="http://localhost:8000"
CLINIC_ID=1

# Setup demo
echo "Setting up demo data..."
curl -X POST $BASE_URL/demo/setup

# Login
echo "Logging in..."
TOKEN=$(curl -X POST $BASE_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' \
  | jq -r '.access_token')

echo "Token: $TOKEN"

# Get clinic stats
echo "Getting clinic stats..."
curl -X GET $BASE_URL/api/clinics/$CLINIC_ID/stats \
  -H "Authorization: Bearer $TOKEN" | jq

# Create service
echo "Creating service..."
curl -X POST $BASE_URL/api/billing/$CLINIC_ID/services \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Service",
    "price": 100,
    "tax_percentage": 10
  }' | jq

echo "Tests complete!"
```