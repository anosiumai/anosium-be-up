# Quick Fix for Missing Columns
# Run this in PostgreSQL (psql) or pgAdmin

-- Add missing columns with IF NOT EXISTS to avoid errors if they're already there
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS discount_reason TEXT;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS appointment_time TIME;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS city VARCHAR(100);

-- Verify the columns were added
SELECT 
    'invoices' as table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name = 'invoices' AND column_name = 'discount_reason'
UNION ALL
SELECT 
    'appointments' as table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name = 'appointments' AND column_name = 'appointment_time'
UNION ALL
SELECT 
    'patients' as table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name = 'patients' AND column_name = 'city';