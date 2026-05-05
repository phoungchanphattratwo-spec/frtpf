import json, os, tempfile

mf = os.path.join(tempfile.gettempdir(), 'frt_device_account_mapping.json')
mapping = json.load(open(mf))
print('Current mapping UIDs:', {k: v['uid'] for k,v in mapping.items()})

backup = 'account_backup'
for folder in os.listdir(backup):
    jp = os.path.join(backup, folder, 'account_info.json')
    if os.path.exists(jp):
        d = json.load(open(jp, encoding='utf-8'))
        uid = d.get('account_uid', d.get('uid', d.get('id','')))
        device = d.get('device','')
        print(f'  backup uid={uid}, device_field={device}')
