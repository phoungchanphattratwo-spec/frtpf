with open('gui.py', encoding='utf-8') as f:
    lines = f.readlines()
# Remove lines 17016 to 17039 (0-indexed: 17015 to 17039)
del lines[17015:17039]
with open('gui.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
