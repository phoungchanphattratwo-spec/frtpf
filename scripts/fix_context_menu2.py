#!/usr/bin/env python3
"""Fix corrupted context menu code in gui.py"""

with open('gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 14048 - remove corrupted text
if 14047 < len(lines) and 'returnat cursor position' in lines[14047]:
    lines[14047] = '            return\n'
    print(f"Fixed line 14048: removed corrupted text")

# Remove duplicate lines 14049-14051
if 14048 < len(lines) and 'action = menu.exec(self.account_table.viewport()' in lines[14048]:
    del lines[14048:14051]  # Remove 3 duplicate lines
    print(f"Removed duplicate lines 14049-14051")

# Fix line that should have uids definition and if statement
for i in range(14050, 14060):
    if i < len(lines) and 'rows = self.account_table.selectionModel().selectedRows()' in lines[i]:
        # Check if next line is missing uids and if statement
        if i+1 < len(lines) and 'self.account_table.selectAll()' in lines[i+1]:
            # Insert missing lines
            lines.insert(i+1, '        uids = [self.account_table.item(r.row(), 1).text() for r in rows if self.account_table.item(r.row(), 1)]\n')
            lines.insert(i+2, '        \n')
            lines.insert(i+3, '        if action == select_all_action:\n')
            print(f"Added missing uids definition and if statement after line {i+1}")
        break

# Write to new file
with open('gui_fixed.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✓ Created gui_fixed.py - please close gui.py in editor, then rename gui_fixed.py to gui.py")
