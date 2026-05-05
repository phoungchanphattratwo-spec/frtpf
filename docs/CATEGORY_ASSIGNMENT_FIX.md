# Category Assignment Feature Fix

## Problem
After creating custom categories, users couldn't move accounts into those categories. The feature existed in the code but was not accessible through the UI.

## Root Cause Analysis

### Issues Found:
1. **Missing Menu Item**: The context menu in the account table had no "Assign Category" option
2. **Wrong Column Index**: The `assign_category_to_accounts()` function was using wrong column indices (email/phone columns instead of UID)
3. **No Menu Handler**: Even though the function existed, there was no code to trigger it from the context menu

## Solution Implemented

### 1. Added "Assign Category" Menu to Context Menu
**Location**: `src/ui/mixins/account_mixin.py` - `show_account_context_menu()`

Added a new submenu with:
- **Icon**: Purple tag icon for visual identification
- **"None (Remove Category)"**: Option to remove category assignment
- **Dynamic Category List**: Automatically loads all custom categories
- **Empty State**: Shows "No categories available" when no categories exist

```python
# ── Category ──────────────────────────────────────────────────────
category_menu = menu.addMenu(qta.icon('fa5s.tag', color='#9C27B0'), "Assign Category")
category_none_action = category_menu.addAction(qta.icon('fa5s.times', color='#f44336'), "None (Remove Category)")
category_menu.addSeparator()
# Add custom categories
custom_categories = self.load_custom_categories()
category_actions = {}
for cat in custom_categories:
    cat_action = category_menu.addAction(qta.icon('fa5s.tag', color='#9C27B0'), cat)
    category_actions[cat_action] = cat
```

### 2. Added Menu Action Handlers
**Location**: `src/ui/mixins/account_mixin.py` - `show_account_context_menu()`

Added handlers to process category selection:
```python
# ── Category Assignment ───────────────────────────────────────────
elif action == category_none_action:
    # Remove category from selected accounts
    self.assign_category_to_accounts(selected_rows, "")
elif action in category_actions:
    # Assign selected category to accounts
    selected_category = category_actions[action]
    self.assign_category_to_accounts(selected_rows, selected_category)
```

### 3. Fixed `assign_category_to_accounts()` Function
**Location**: `src/ui/mixins/account_mixin.py`

#### Changes Made:
- **Fixed Column Index**: Changed from email/phone columns (2, 3) to UID column (1)
- **Simplified Logic**: Use UID directly instead of complex email/phone matching
- **Better Error Handling**: More robust UID matching with fallbacks
- **Remove Category Support**: Empty string removes the category field
- **Better Feedback**: Activity log messages instead of popup dialogs
- **UTF-8 Support**: Added `ensure_ascii=False` for proper encoding

#### Column Structure:
```
Column 0: #
Column 1: UID          ← Used for matching
Column 2: Password
Column 3: Email
Column 4: Phone
Column 5: Name
Column 6: Pass/Mail
Column 7: Cookie
Column 8: 2FA
Column 9: Created
```

## How It Works Now

### User Workflow:
1. **Create Categories**: Click "Manage Categories" button to create custom categories
2. **Select Accounts**: Select one or more accounts in the account table
3. **Right-Click**: Open context menu
4. **Assign Category**: Navigate to "Assign Category" → Select a category
5. **Confirmation**: Activity log shows success message
6. **Filter**: Use the category filter dropdown to view accounts by category

### Technical Flow:
1. User selects category from context menu
2. Handler calls `assign_category_to_accounts(selected_rows, category_name)`
3. Function iterates through selected rows
4. Extracts UID from column 1
5. Finds matching `account_info.json` file in `account_backup/` folder
6. Updates or removes the `category` field in JSON
7. Saves file with UTF-8 encoding
8. Refreshes account table to show changes
9. Displays activity log message

### Category Storage:
Categories are stored in each account's `account_info.json`:
```json
{
    "account_uid": "61586927747389",
    "email": "example@outlook.com",
    "password": "password123",
    "category": "VIP Accounts",  ← Category field
    ...
}
```

## Features

### ✅ Assign Category
- Select single or multiple accounts
- Right-click → "Assign Category" → Choose category
- Category is saved to account data
- Table refreshes automatically

### ✅ Remove Category
- Select accounts with categories
- Right-click → "Assign Category" → "None (Remove Category)"
- Category field is removed from account data

### ✅ Filter by Category
- Use category dropdown filter at top of account tab
- Shows only accounts with selected category
- "All" shows all accounts regardless of category

### ✅ Smart Matching
- Uses UID for reliable account identification
- Handles missing or malformed data gracefully
- Supports bulk operations (multiple accounts at once)

## Testing Checklist

- [x] Create custom categories
- [x] Assign category to single account
- [x] Assign category to multiple accounts
- [x] Remove category from accounts
- [x] Filter accounts by category
- [x] Verify category persists after app restart
- [x] Handle accounts without UID gracefully
- [x] UTF-8 category names work correctly

## Related Files
- `src/ui/mixins/account_mixin.py` - Main implementation
- `gui.py` - Account table structure
- `account_backup/*/account_info.json` - Category storage

## Benefits
- **Organized Accounts**: Group accounts by purpose (VIP, Testing, Production, etc.)
- **Easy Filtering**: Quickly find accounts by category
- **Bulk Operations**: Assign categories to multiple accounts at once
- **Flexible**: Add/remove categories anytime
- **Persistent**: Categories saved with account data
