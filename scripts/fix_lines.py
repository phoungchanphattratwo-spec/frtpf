lines = open('gui.py', encoding='utf-8').readlines()
# Remove lines 12140, 12141, 12142 (indices 12139, 12140, 12141)
del lines[12139:12142]
open('gui.py', 'w', encoding='utf-8').writelines(lines)
print('Fixed, removed lines 12140-12142')
