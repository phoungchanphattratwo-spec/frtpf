# License Management Dashboard

A secure, modern web dashboard for managing software licenses with Supabase integration.

## 🔐 Security Features

- **Protected Supabase Credentials** - API keys never exposed in code
- **Session-based Authentication** - Credentials stored securely in browser session
- **Admin Password Protection** - Additional security layer
- **Auto-redirect** - Unauthorized users redirected to login
- **1-hour Session Timeout** - Automatic logout for security
- **Connection Verification** - Tests Supabase credentials before login

## 🚀 Getting Started

### 1. Setup Supabase Database

Run the SQL schema in your Supabase SQL Editor:
- Open `../supabase_schema.sql`
- Copy all SQL code
- Paste in Supabase SQL Editor
- Click "Run"

### 2. Configure Auto-Fill (Optional but Recommended)

The `config.js` file is already set up with your credentials and will auto-fill the login form!

**To enable auto-login (skip login page entirely):**

1. Open `config.js`
2. Change line 8:
```javascript
autoLogin: true,  // Change from false to true
```
3. Save the file
4. Now when you open `login.html`, it will automatically log you in!

**Note:** The `config.js` file is in `.gitignore` so it won't be shared if you commit to git.

### 3. Access the Dashboard

**Option A: With Auto-Fill (default)**
1. Open `login.html`
2. Fields are pre-filled with your credentials
3. Just enter admin password: `FRT@2024!Secure`
4. Click "Sign In"

**Option B: With Auto-Login (if enabled)**
1. Open `login.html`
2. Automatically logs in and redirects to dashboard
3. No manual input needed!

### 4. Change Admin Password (IMPORTANT!)

For security, change the default admin password:

1. Open `auth.js`
2. Find line 3:
```javascript
adminPassword: 'FRT@2024!Secure',
```
3. Change to your secure password:
```javascript
adminPassword: 'YourSecurePassword123!',
```
4. Save the file

## 📁 File Structure

```
license_dashboard/
├── login.html          # Login page
├── login.css           # Login page styles
├── auth.js             # Authentication logic
├── index.html          # Main dashboard
├── styles.css          # Dashboard styles
├── app.js              # Dashboard functionality
└── README.md           # This file
```

## ✨ Features

### Security
- ✅ **No hardcoded API keys** - Credentials entered at login
- ✅ Supabase credentials stored in encrypted session
- ✅ Admin password protection
- ✅ Connection verification before access
- ✅ Auto-logout after 1 hour
- ✅ Protected dashboard access

### License Management
- ✅ View all licenses with statistics
- ✅ Create new licenses (auto-generated keys)
- ✅ Edit existing licenses
- ✅ Delete licenses
- ✅ Search and filter
- ✅ Status tracking (Active, Expired, Deactivated)

### Dashboard Statistics
- Total Licenses
- Active Licenses
- Expired Licenses
- Expiring Soon (30 days)

## 🔧 Configuration

### Change Session Timeout

Edit `auth.js` and `app.js`:

```javascript
sessionTimeout: 3600000  // 1 hour (in milliseconds)
```

Examples:
- 30 minutes: `1800000`
- 2 hours: `7200000`
- 24 hours: `86400000`

### Supabase Configuration

Edit `app.js` to update Supabase credentials:

```javascript
const SUPABASE_URL = 'your-project-url';
const SUPABASE_KEY = 'your-anon-key';
```

## 🛡️ Security Best Practices

1. **Change admin password immediately** in `auth.js`
2. **Never share Supabase credentials** publicly
3. **Use strong admin passwords** (minimum 12 characters)
4. **Don't commit credentials** to version control
5. **Use HTTPS** when deploying to production
6. **Enable Row Level Security** in Supabase
7. **Regular password updates** (every 90 days)
8. **Clear browser data** when using shared computers

## 🔒 How Security Works

1. **Login**: Admin enters Supabase URL, API key, and admin password
2. **Verification**: System tests connection to Supabase
3. **Encryption**: Credentials are Base64 encoded and stored in session
4. **Session**: Valid for 1 hour, then auto-logout
5. **Dashboard**: Retrieves credentials from session (never from code)
6. **Logout**: Clears all session data

**Key Point**: Supabase credentials are NEVER stored in the JavaScript files - they're entered at login and stored only in the browser session.

## 📝 Usage

### Login
1. Navigate to `login.html`
2. Enter username and password
3. Click "Sign In"

### Create License
1. Click "Create License" button
2. License key and Tool ID are auto-generated
3. Select license type
4. Set expiry date
5. Add optional notes
6. Click "Save License"

### Edit License
1. Find license in table
2. Click "Edit" button
3. Modify fields
4. Click "Save License"

### Delete License
1. Find license in table
2. Click "Delete" button
3. Confirm deletion

### Search Licenses
- Type in search box to filter by:
  - License key
  - Tool ID
  - User name
  - License type

### Logout
- Click "Logout" button in header
- Confirm logout

## 🔍 Troubleshooting

### Can't Login
- Check username and password are correct
- Check browser console for errors
- Clear browser cache and try again

### Dashboard Not Loading
- Ensure you're logged in
- Check Supabase credentials in `app.js`
- Verify SQL schema was run in Supabase
- Check browser console for errors

### Session Expired
- Login again
- Session expires after 1 hour of inactivity

## 📞 Support

For issues or questions:
- Telegram: [@ftoolpro](https://t.me/ftoolpro)

## 📄 License

This dashboard is part of the Facebook Register Tool (FRT) project.

---

**Default Admin Password:** `FRT@2024!Secure`

**⚠️ IMPORTANT:** 
- Change the admin password in `auth.js` immediately!
- Never commit your Supabase credentials to version control
- Supabase credentials are entered at login, not stored in code
