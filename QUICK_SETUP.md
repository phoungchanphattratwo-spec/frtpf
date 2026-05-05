# Quick Setup Guide - License System

## ✅ Configuration Complete!

Your Supabase credentials are now configured:
- **Project URL:** `https://ntudetvfgwnnhqluwaqe.supabase.co` ✅
- **API Key:** Configured ✅

---

## 🗄️ Step 1: Set Up Database (REQUIRED)

1. Go to your Supabase dashboard: https://supabase.com/dashboard/project/ntudetvfgwnnhqluwaqe
2. Click **SQL Editor** in the left sidebar
3. Click **New Query**
4. Copy the entire contents of `supabase_schema.sql`
5. Paste it into the SQL editor
6. Click **Run** (or press Ctrl+Enter)
7. You should see: "Success. No rows returned"

### Verify Table Creation

1. Go to **Table Editor** in the left sidebar
2. You should see a new table called **`licenses`**
3. Click on it to view the structure

---

## 🔑 Step 2: Create Your First License

### Option A: Using Supabase Dashboard (Easy)

1. Go to **Table Editor** → **licenses**
2. Click **Insert** → **Insert row**
3. Fill in the following fields:

   ```
   license_key: TEST-DEMO-2024-ABCD
   tool_id: FRT-2024-0001
   license_type: Professional
   expiry_date: 2026-12-31 23:59:59+00
   is_active: true (checked)
   is_activated: false (unchecked)
   ```

4. Leave other fields empty (they'll auto-fill)
5. Click **Save**

### Option B: Using SQL (Advanced)

Run this in SQL Editor:

```sql
-- Create a test license
INSERT INTO public.licenses (
    license_key,
    tool_id,
    license_type,
    expiry_date,
    is_active,
    notes
) VALUES (
    'TEST-DEMO-2024-ABCD',
    'FRT-2024-0001',
    'Professional',
    '2026-12-31 23:59:59+00',
    true,
    'Test license for development'
);
```

### Option C: Generate Random License Key

```sql
-- Generate and insert a random license
INSERT INTO public.licenses (
    license_key,
    tool_id,
    license_type,
    expiry_date
) VALUES (
    generate_license_key(),  -- Auto-generates: XXXX-XXXX-XXXX-XXXX
    'FRT-2024-0001',
    'Professional',
    NOW() + INTERVAL '1 year'
);

-- View the generated key
SELECT license_key, tool_id, expiry_date 
FROM licenses 
ORDER BY created_at DESC 
LIMIT 1;
```

---

## 📦 Step 3: Install Dependencies

```bash
pip install requests
```

---

## 🔗 Step 4: Integrate into Your App

### Add to gui.py (at the top with other imports):

```python
from src.core.license_manager import LicenseManager
from src.core.license_config import SUPABASE_URL, SUPABASE_KEY
from src.ui.license_dialog import LicenseActivationDialog
```

### Add to MainWindow.__init__ (after super().__init__()):

```python
# Initialize license manager
self.license_manager = LicenseManager(SUPABASE_URL, SUPABASE_KEY)

# Check license on startup
QTimer.singleShot(100, self._check_license_on_startup)
```

### Add these methods to MainWindow class:

```python
def _check_license_on_startup(self):
    """Check license validity on application startup."""
    is_valid, message, license_data = self.license_manager.validate_license(offline_mode=False)
    
    if not is_valid:
        # Show activation dialog
        dialog = LicenseActivationDialog(self.license_manager, self)
        dialog.license_activated.connect(self._on_license_activated)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            # User cancelled - close application
            QMessageBox.critical(
                self,
                "License Required",
                "A valid license is required to use this software.\n\n"
                f"Machine ID: {self.license_manager.get_machine_id()}"
            )
            sys.exit(0)
    else:
        # License is valid
        self._on_license_activated(license_data)

def _on_license_activated(self, license_data):
    """Called when license is successfully activated."""
    if license_data:
        self.add_activity(f"✓ License activated: {license_data.get('license_type', 'Professional')}")
        # Update UI with license info if needed
```

---

## 🧪 Step 5: Test the System

### Test 1: First Launch (Activation)
1. Run your application
2. You should see the license activation dialog
3. Enter your test license key: `TEST-DEMO-2024-ABCD`
4. Enter your name (optional)
5. Click "Activate License"
6. Should show success message

### Test 2: Subsequent Launches (Validation)
1. Close the application
2. Run it again
3. Should NOT ask for license (validates from cache)
4. Should start normally

### Test 3: View License Info
1. Click the license key icon (🔑) in the title bar
2. Should show your license details
3. Verify all information is correct

### Test 4: Check in Supabase
1. Go to **Table Editor** → **licenses**
2. Find your license
3. Should see:
   - `is_activated`: true ✅
   - `machine_id`: (your machine hash)
   - `activated_at`: (timestamp)
   - `user_name`: (your name)

---

## 🎯 Quick Checklist

- [x] Got Supabase Project URL ✅
- [x] Updated `src/core/license_config.py` with URL ✅
- [ ] Ran `supabase_schema.sql` in SQL Editor
- [ ] Created test license in database
- [ ] Installed `requests` package
- [ ] Added imports to `gui.py`
- [ ] Added license manager initialization
- [ ] Added license check methods
- [ ] Tested activation flow
- [ ] Verified in Supabase dashboard

---

## 🆘 Common Issues

### "Failed to verify license: 404"
- Your Supabase URL is incorrect
- Check Settings → API for correct URL

### "Invalid license key"
- License key doesn't exist in database
- Check spelling and format (XXXX-XXXX-XXXX-XXXX)

### "License key is already activated on another machine"
- License is bound to different machine
- In Supabase, set `machine_id` to NULL and `is_activated` to false
- Try activating again

### "Network error"
- Check internet connection
- Verify Supabase project is active
- Check if API key is correct

---

## 📞 Need Help?

If you encounter issues:
1. Check the detailed guide: `LICENSE_SYSTEM_README.md`
2. Verify all steps above are completed
3. Check Supabase logs in dashboard
4. Contact support: [@ftoolpro](https://t.me/ftoolpro)

---

## 🎉 You're All Set!

Once you complete these steps, your license system will be fully functional!

**Your API Key:** ✅ Configured  
**Your Project URL:** ✅ Configured (`https://ntudetvfgwnnhqluwaqe.supabase.co`)  
**Database Schema:** ⏳ Needs to be created (Step 1)  
**Test License:** ⏳ Needs to be created (Step 2)  
**Integration:** ⏳ Needs to be added to gui.py (Step 4)
