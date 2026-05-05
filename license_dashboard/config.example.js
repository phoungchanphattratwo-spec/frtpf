// Local Configuration File - EXAMPLE
// Copy this file to 'config.js' and fill in your credentials

const LOCAL_CONFIG = {
    // Your Supabase credentials - auto-fills login form
    supabaseUrl: 'https://xxxxx.supabase.co',
    supabaseKey: 'your-supabase-anon-key-here',
    
    // Set to true to auto-login (skip login page entirely)
    autoLogin: true
};

// Auto-fill login form when page loads
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        // Check if we're on login page
        if (document.getElementById('supabaseUrl')) {
            // Auto-fill the form fields
            document.getElementById('supabaseUrl').value = LOCAL_CONFIG.supabaseUrl;
            document.getElementById('supabaseKey').value = LOCAL_CONFIG.supabaseKey;
            
            // If autoLogin is enabled, submit the form automatically
            if (LOCAL_CONFIG.autoLogin) {
                // Auto-submit after a short delay
                setTimeout(() => {
                    const form = document.getElementById('loginForm');
                    if (form) {
                        form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                    }
                }, 500);
            }
        }
    });
}
