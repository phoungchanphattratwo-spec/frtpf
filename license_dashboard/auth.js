// Authentication Configuration
const AUTH_CONFIG = {
    sessionKey: 'license_dashboard_auth',
    sessionTimeout: 3600000 // 1 hour in milliseconds
};

// Handle login form submission
async function handleLogin(event) {
    event.preventDefault();
    
    const supabaseUrl = document.getElementById('supabaseUrl').value.trim();
    const supabaseKey = document.getElementById('supabaseKey').value.trim();
    const loginBtn = document.getElementById('loginBtn');
    
    // Disable button during login
    loginBtn.disabled = true;
    loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';
    
    // Validate Supabase URL format
    if (!supabaseUrl.includes('supabase.co')) {
        showError('Invalid Supabase URL format', loginBtn);
        return;
    }
    
    // Store credentials and redirect (skip connection test for now)
    const session = {
        authenticated: true,
        supabaseUrl: btoa(supabaseUrl), // Base64 encode
        supabaseKey: btoa(supabaseKey), // Base64 encode
        loginTime: Date.now()
    };
    
    // Store session
    sessionStorage.setItem(AUTH_CONFIG.sessionKey, JSON.stringify(session));
    
    // Redirect to dashboard
    setTimeout(() => {
        window.location.href = 'index.html';
    }, 500);
}

// Show error message
function showError(message, loginBtn) {
    const errorMessage = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');
    
    errorText.textContent = message;
    errorMessage.style.display = 'flex';
    
    loginBtn.disabled = false;
    loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Sign In';
    
    // Clear sensitive fields
    document.getElementById('supabaseKey').value = '';
}

// Check if user is already logged in (for login page)
function checkExistingSession() {
    const session = getSession();
    if (session && isSessionValid(session)) {
        // Already logged in, redirect to dashboard
        window.location.href = 'index.html';
    }
}

// Get session from storage
function getSession() {
    try {
        const sessionData = sessionStorage.getItem(AUTH_CONFIG.sessionKey);
        return sessionData ? JSON.parse(sessionData) : null;
    } catch (error) {
        return null;
    }
}

// Check if session is valid
function isSessionValid(session) {
    if (!session || !session.authenticated) {
        return false;
    }
    
    const currentTime = Date.now();
    const sessionAge = currentTime - session.loginTime;
    
    // Check if session has expired
    if (sessionAge > AUTH_CONFIG.sessionTimeout) {
        clearSession();
        return false;
    }
    
    return true;
}

// Clear session
function clearSession() {
    sessionStorage.removeItem(AUTH_CONFIG.sessionKey);
}

// Check authentication on login page load
if (window.location.pathname.includes('login.html')) {
    checkExistingSession();
}
