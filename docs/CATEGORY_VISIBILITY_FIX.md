# Category Visibility Fix

## Problem
When users create categories in the "Manage Categories" dialog, the categories don't appear in the category filter dropdown.

## Root Cause Analysis

### Issues Found:
1. **Message Box Blocking**: The success message box was shown before the dialog closed, potentially blocking the refresh
2. **No Debug Output**: No logging to verify if categories were being saved/loaded correctly
3. **Signal Interference**: Category filter signals weren't blocked during refresh, potentially causing issues
4. **Missing Error Handling**: No feedback if save/load operations failed

## Solution Implemented

### 1. Fixed Save Order
**Location**: `src/ui/mixins/account_mixin.py` - `save_categories_from_dialog()`

Changed the order of operations:
```python
# OLD ORDER (problematic):
self.save_custom_categories(categories)
self.refresh_category_filter()
dialog.accept()
QMessageBox.information(...)  # Blocks everything!

# NEW ORDER (fixed):
self.save_custom_categories(categories)
dialog.accept()                # Close dialog first
self.refresh_category_filter() # Then refresh
self.add_activity(...)         # Non-blocking feedback
```

### 2. Added Debug Logging
**Locations**: 
- `load_custom_categories()` - Logs how many categories were loaded
- `save_custom_categories()` - Logs save success/failure
- `refresh_category_filter()` - Logs each category being added

This helps diagnose issues:
```python
print(f"[Categories] Loaded {len(categories)} categories from {CONFIG_FILE}")
print(f"[Categories] Saved {len(categories)} categories to {CONFIG_FILE}")
print(f"[Refresh] Adding {len(custom_categories)} custom categories to filter")
```

### 3. Improved Refresh Logic
**Location**: `src/ui/mixins/account_mixin.py` - `refresh_category_filter()`

Added signal blocking to prevent interference:
```python
# Block signals during refresh
self.account_category_filter.blockSignals(True)
self.account_category_filter.clear()
# ... add items ...
self.account_category_filter.blockSignals(False)
```

### 4. Better Error Handling
Added try-catch blocks and error reporting:
- Save failures now show activity log message
- Load failures are logged to console
- Refresh failures show user-friendly error

### 5. UTF-8 Encoding
Added proper encoding to support international characters:
```python
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    config = json.load(f)

with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=4, ensure_ascii=False)
```

## Config File Location

Categories are stored in:
```
Windows: C:\Users\<USERNAME>\AppData\Local\Temp\frt_config.json
```

Format:
```json
{
  "account_categories": [
    "VIP",
    "Testing",
    "Production"
  ]
}
```

## Testing

### Test Script Created
**File**: `test_categories.py`

Run this script to:
- Check config file location
- Verify categories are saved
- Create test categories if needed

```bash
python test_categories.py
```

### Manual Testing Steps:
1. **Create Category**:
   - Click "Manage Categories" button
   - Type category name (e.g., "VIP")
   - Click "Add" button
   - Click "Save" button
   - Check activity log for success message

2. **Verify Visibility**:
   - Look at category filter dropdown
   - Should see: All, Email, Phone, ---, VIP
   - Check console output for debug messages

3. **Assign Category**:
   - Select account(s)
   - Right-click → "Assign Category" → "VIP"
   - Verify category is assigned

4. **Filter by Category**:
   - Select "VIP" from category dropdown
   - Only VIP accounts should show

## Debug Output Example

When working correctly, you should see:
```
[Categories] Saved 3 categories to C:\Users\...\Temp\frt_config.json
[Categories] Loaded 3 categories from C:\Users\...\Temp\frt_config.json
[Refresh] Adding 3 custom categories to filter
  - Added: VIP
  - Added: Testing
  - Added: Production
[Refresh] Category filter now has 7 items
```

## Troubleshooting

### Categories Not Showing?

1. **Check Console Output**:
   - Look for "[Categories]" and "[Refresh]" messages
   - Verify categories are being loaded

2. **Check Config File**:
   - Run `test_categories.py` to see file location
   - Open file and verify JSON structure

3. **Check Permissions**:
   - Ensure app can write to temp directory
   - Try running as administrator if needed

4. **Restart App**:
   - Close and reopen the application
   - Categories should persist

### Common Issues:

**Issue**: Categories save but don't appear
- **Cause**: Refresh not called or failed
- **Solution**: Check console for error messages

**Issue**: Config file not found
- **Cause**: First time use or temp directory cleared
- **Solution**: Create categories again, they'll be saved

**Issue**: Categories disappear after restart
- **Cause**: Config file deleted or temp directory cleaned
- **Solution**: Use persistent config location (future enhancement)

## Future Enhancements

1. **Persistent Storage**: Move config to app directory instead of temp
2. **Category Colors**: Allow users to assign colors to categories
3. **Category Icons**: Add icon selection for visual identification
4. **Bulk Category Assignment**: Import categories from file
5. **Category Statistics**: Show account count per category

## Related Files
- `src/ui/mixins/account_mixin.py` - Main implementation
- `src/core/config.py` - Config file management
- `test_categories.py` - Testing utility
- `docs/CATEGORY_ASSIGNMENT_FIX.md` - Assignment feature documentation
