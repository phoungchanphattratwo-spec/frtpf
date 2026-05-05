# Missing Account Names - Root Cause & Solution

## Problem

After importing 21 accounts using `convert_tar_to_import_format.py`, some accounts show names (like "Anna Joanna", "Jack Michael") while others show "—" (dash) in the UI.

## Root Cause

The account names are **NOT stored in the Profile tar files**. The tar files only contain:
- Facebook session data (authentication, cookies, databases)
- Device information
- App preferences

The names must be provided separately through the `account_info.json` file.

### Why Some Accounts Have Names

Accounts that show names fall into two categories:

1. **Accounts from original backup folder** - These were backed up by the tool itself, which extracted names from Facebook's API during backup
2. **Manually edited accounts** - Someone manually added names to the `account_info.json` files

### Why Some Accounts Show "—"

The `convert_tar_to_import_format.py` script creates placeholder names:
```python
"full_name": f"Account {uid}"
```

When the tool loads accounts with empty `full_name` or placeholder names, it displays "—" in the UI.

## Affected Accounts

Accounts showing "—" (dash):
- 61587361227186
- 61587432923414
- 61587462509485
- 61587157337329
- 61587593545795
- 61587333099275
- 61587610855850
- 61587311951331
- 61587255044198
- 61587414366357
- 61587189467214

## Solutions

### Option 1: Manual Update (Recommended for Small Numbers)

Run the `update_account_names.py` script:

```bash
python update_account_names.py
```

Select option 1 (Manual mode) and enter names for each account when prompted.

### Option 2: CSV Import (Recommended for Large Numbers)

1. Create a CSV file with UID and Name columns:

```csv
UID,Name
61587361227186,John Smith
61587432923414,Jane Doe
61587462509485,Bob Johnson
```

2. Run the script:

```bash
python update_account_names.py
```

3. Select option 2 (CSV mode) and provide the CSV file path

### Option 3: Direct JSON Edit

Manually edit each `account_backup/[UID]_*/account_info.json` file:

```json
{
    "account_uid": "61587361227186",
    "full_name": "John Smith",
    "first_name": "John",
    "last_name": "Smith",
    ...
}
```

## Where to Get Names

Since names aren't in the tar files, you need to get them from:

1. **Original source** - Where you got the tar files from
2. **Facebook login** - Log into each account and check the profile
3. **Email/Phone records** - Match UIDs to your account records
4. **Cookies** - Some accounts have email in the `account_info.json` cookies field

## Checking Cookies for Clues

Some `account_info.json` files have email addresses in the cookies field:

```json
"cookies": "|nannzin1+zdesj55@zohomail.com|D2gLk7bCPTFN|..."
```

This email might help you identify the account owner.

## After Updating Names

1. **Close the tool** if it's running
2. **Restart the tool** to reload account data
3. **Verify** that names now appear in the account list

## Prevention for Future Imports

When creating backups in the future:
1. Use the tool's built-in backup feature (it extracts names automatically)
2. OR: Keep a separate CSV/spreadsheet mapping UIDs to names
3. OR: Include names in the tar filename (e.g., `61587361227186_JohnSmith.tar.gz`)

## Technical Details

### Account Display Logic

The tool displays account names from `account_info.json`:
- If `full_name` is empty or starts with "Account ", shows "—"
- Otherwise, shows the `full_name` value

### Name Storage

Names are stored in three places in `account_info.json`:
```json
{
    "full_name": "John Smith",    // Used for display
    "first_name": "John",          // Used for filtering
    "last_name": "Smith"           // Used for filtering
}
```

## Files

- `update_account_names.py` - Script to update names manually or from CSV
- `convert_tar_to_import_format.py` - Original conversion script (creates placeholders)
- `account_backup/*/account_info.json` - Where names are stored
