with open('gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

replacements = {
    14360: '        self.seed_react_like_cb  = QCheckBox("Like");  self.seed_react_like_cb.setStyleSheet(_CHECK_STYLE);  self.seed_react_like_cb.setChecked(True)\n',
    14361: '        self.seed_react_love_cb  = QCheckBox("Love");  self.seed_react_love_cb.setStyleSheet(_CHECK_STYLE)\n',
    14362: '        self.seed_react_care_cb  = QCheckBox("Care");  self.seed_react_care_cb.setStyleSheet(_CHECK_STYLE)\n',
    14363: '        self.seed_react_haha_cb  = QCheckBox("Haha");  self.seed_react_haha_cb.setStyleSheet(_CHECK_STYLE)\n',
    14364: '        self.seed_react_wow_cb   = QCheckBox("Wow");   self.seed_react_wow_cb.setStyleSheet(_CHECK_STYLE)\n',
    14365: '        self.seed_react_sad_cb   = QCheckBox("Sad");   self.seed_react_sad_cb.setStyleSheet(_CHECK_STYLE)\n',
    14366: '        self.seed_react_angry_cb = QCheckBox("Angry"); self.seed_react_angry_cb.setStyleSheet(_CHECK_STYLE)\n',
}
for idx, val in replacements.items():
    lines[idx] = val

with open('gui.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
