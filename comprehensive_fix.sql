-- Comprehensive fix for ALL missing columns
-- Run this against your PostgreSQL database

-- Fix invoices table
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS discount_reason TEXT;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS terms_conditions TEXT;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS created_by INTEGER;

-- Fix appointments table
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS appointment_time TIME;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS appointment_type VARCHAR(50);
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS ai_lead_id INTEGER;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMP;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS cancellation_reason TEXT;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS created_by INTEGER;

-- Fix patients table
ALTER TABLE patients ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS state VARCHAR(100);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS chronic_conditions TEXT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS emergency_contact_name VARCHAR(200);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS emergency_contact_phone VARCHAR(20);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS registration_date DATE DEFAULT CURRENT_DATE;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS referred_by VARCHAR(200);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS notes TEXT;

-- Verify all columns were added
SELECT 
    table_name,
    column_name,
    data_type,
    character_maximum_length
FROM information_schema.columns 
WHERE 
    (table_name = 'invoices' AND column_name IN ('discount_reason', 'terms_conditions', 'created_by'))
    OR (table_name = 'appointments' AND column_name IN ('appointment_time', 'appointment_type', 'ai_lead_id', 'checked_in_at', 'completed_at', 'cancelled_at', 'cancellation_reason', 'created_by'))
    OR (table_name = 'patients' AND column_name IN ('city', 'state', 'postal_code', 'chronic_conditions', 'emergency_contact_name', 'emergency_contact_phone', 'registration_date', 'referred_by', 'notes'))
ORDER BY table_name, column_name;