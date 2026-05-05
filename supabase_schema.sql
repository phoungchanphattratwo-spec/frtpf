-- Supabase License Management Schema
-- Run this SQL in your Supabase SQL Editor to create the licenses table

-- Create licenses table
CREATE TABLE IF NOT EXISTS public.licenses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    license_key TEXT UNIQUE NOT NULL,
    tool_id TEXT NOT NULL,
    license_type TEXT DEFAULT 'Professional',
    user_name TEXT,
    machine_id TEXT,
    is_active BOOLEAN DEFAULT true,
    is_activated BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    activated_at TIMESTAMP WITH TIME ZONE,
    deactivated_at TIMESTAMP WITH TIME ZONE,
    expiry_date TIMESTAMP WITH TIME ZONE NOT NULL,
    last_validated TIMESTAMP WITH TIME ZONE,
    max_activations INTEGER DEFAULT 1,
    notes TEXT
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_licenses_license_key ON public.licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_licenses_machine_id ON public.licenses(machine_id);
CREATE INDEX IF NOT EXISTS idx_licenses_expiry ON public.licenses(expiry_date);

-- Enable Row Level Security (RLS)
ALTER TABLE public.licenses ENABLE ROW LEVEL SECURITY;

-- Create policy to allow read access with valid API key
CREATE POLICY "Allow read access for valid API key" ON public.licenses
    FOR SELECT
    USING (true);

-- Create policy to allow update for activation
CREATE POLICY "Allow update for activation" ON public.licenses
    FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- Create policy to allow insert (for admin only - you can restrict this)
CREATE POLICY "Allow insert for service role" ON public.licenses
    FOR INSERT
    WITH CHECK (true);

-- Function to generate license keys
CREATE OR REPLACE FUNCTION generate_license_key()
RETURNS TEXT AS $$
DECLARE
    chars TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    result TEXT := '';
    i INTEGER;
BEGIN
    FOR i IN 1..4 LOOP
        IF i > 1 THEN
            result := result || '-';
        END IF;
        result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
        result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
        result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
        result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Example: Insert sample licenses
-- Uncomment and modify as needed

/*
INSERT INTO public.licenses (license_key, tool_id, license_type, expiry_date, notes)
VALUES 
    ('DEMO-XXXX-YYYY-ZZZZ', 'FRT-2024-0001', 'Professional', NOW() + INTERVAL '1 year', 'Demo license'),
    ('TEST-AAAA-BBBB-CCCC', 'FRT-2024-0002', 'Professional', NOW() + INTERVAL '1 year', 'Test license');
*/

-- View to check license status
CREATE OR REPLACE VIEW license_status AS
SELECT 
    license_key,
    tool_id,
    license_type,
    user_name,
    machine_id,
    is_active,
    is_activated,
    CASE 
        WHEN expiry_date < NOW() THEN 'Expired'
        WHEN is_activated THEN 'Active'
        ELSE 'Not Activated'
    END as status,
    created_at,
    activated_at,
    expiry_date,
    last_validated,
    EXTRACT(DAY FROM (expiry_date - NOW())) as days_remaining
FROM public.licenses
ORDER BY created_at DESC;

-- Grant access to the view
GRANT SELECT ON license_status TO anon, authenticated;

COMMENT ON TABLE public.licenses IS 'License management table for FRT application';
COMMENT ON COLUMN public.licenses.license_key IS 'Unique license key in format XXXX-XXXX-XXXX-XXXX';
COMMENT ON COLUMN public.licenses.tool_id IS 'Unique tool identifier';
COMMENT ON COLUMN public.licenses.machine_id IS 'Unique machine identifier (SHA256 hash)';
COMMENT ON COLUMN public.licenses.is_active IS 'Whether the license is active (can be deactivated by admin)';
COMMENT ON COLUMN public.licenses.is_activated IS 'Whether the license has been activated on a machine';
COMMENT ON COLUMN public.licenses.max_activations IS 'Maximum number of machines this license can be activated on';
