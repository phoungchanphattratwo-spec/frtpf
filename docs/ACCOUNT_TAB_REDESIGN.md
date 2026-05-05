# Account Tab Redesign - Device-Centric View

## Current Design (Account-Centric)
- Main table shows accounts (10 rows)
- Each row shows: UID, Name, Email, Phone, Password, Birthday, Gender, **Device**, Status, Proxy, Created, Notes
- Problem: Too much account info, device is just one column

## New Design (Device-Centric) ✨

### Main Table: DEVICES
Columns:
1. **#** - Row number
2. **Device ID** - Full device ID (520023fcfef9b4f1)
3. **Model** - Device model (SM-G973N)
4. **Android** - Android version (9)
5. **Battery** - Battery level (85%)
6. **Resolution** - Screen resolution (1080x2280)
7. **Assigned Account** - UID or "Not Assigned"
8. **Account Name** - Name from account
9. **Status** - Device status (Active/Idle)

### Toolbar Buttons
1. **Refresh** - Refresh device list
2. **Account Manager** - Open dialog to view all accounts and assign to devices
3. **Load Devices** - Load devices from ADB
4. **MaxChange** - Quick access to MaxChange menu

### Account Manager Dialog
- Shows all accounts in a table
- Select account → Select device → Click "Assign"
- Can bulk assign accounts to multiple devices
- Shows which accounts are already assigned

## Benefits
1. ✅ Focus on devices (what you actually work with)
2. ✅ Cleaner table (less columns)
3. ✅ Easy to see which devices have accounts
4. ✅ Professional workflow
5. ✅ Account details in separate dialog (not cluttering main view)

## Implementation Plan
1. Modify `open_account_tab()` to create device-centric table
2. Create `open_account_manager_dialog()` for account assignment
3. Update context menu for device operations
4. Keep account backup system unchanged
