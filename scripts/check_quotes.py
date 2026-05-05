lines = open('gui.py', encoding='utf-8').readlines()
content = ''.join(lines[:13692])
count = content.count('"""')
print(f'Triple-quote count: {count}, balanced: {count % 2 == 0}')
pos = 0
positions = []
while True:
    p = content.find('"""', pos)
    if p == -1: break
    line_num = content[:p].count('\n') + 1
    positions.append(line_num)
    pos = p + 3
print('Last 6 triple-quote line numbers:', positions[-6:])
