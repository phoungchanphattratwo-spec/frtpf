# ឧបករណ៍ FRT Tool — ការពិពណ៌នាលម្អិត

ឧបករណ៍នេះគឺជាកម្មវិធី Desktop សម្រាប់ Windows ដែលបង្កើតឡើងដោយ Python + PyQt5 ។ វាត្រូវបានរចនាឡើងដើម្បីគ្រប់គ្រងគណនី Facebook និងឧបករណ៍ Android ច្រើនក្នុងពេលតែមួយ ដោយប្រើ ADB និង Appium ជា backend ។

---

## ១. Dashboard (ផ្ទាំងទិដ្ឋភាពទូទៅ)

- បង្ហាញស្ថិតិសរុប: ចំនួនគណនី, ឧបករណ៍ដែលភ្ជាប់, អត្រាជោគជ័យ
- ត្រួតពិនិត្យស្ថានភាព ADB និងប្រព័ន្ធ (CPU, RAM)
- បង្ហាញ Activity Log ថ្មីៗ
- Ring Chart Widget សម្រាប់បង្ហាញភាគរយ

---

## ២. ការចុះឈ្មោះ Facebook ដោយស្វ័យប្រវត្តិ (Auto Registration)

មុខងារនេះប្រើ Appium ដើម្បីបើក Facebook Lite ឬ Facebook ដើម ហើយចុះឈ្មោះគណនីថ្មីដោយស្វ័យប្រវត្តិ។

**អ្វីដែលអាចកំណត់បាន:**
- ឈ្មោះ (ដំបូង + នាមត្រកូល) — ដោយដៃ, ចៃដន្យ, ឬ English ស្វ័យប្រវត្តិ
- ថ្ងៃខែឆ្នាំកំណើត និងភេទ
- អ៊ីមែល ឬ លេខទូរស័ព្ទ (ជ្រើសរើសបាន)
- ពាក្យសម្ងាត់ — ដោយដៃ ឬ ចៃដន្យ
- ជ្រើសរើស Facebook Lite ឬ Facebook ដើម
- ចំនួនគណនីដែលត្រូវចុះឈ្មោះ, ការ delay, parallel, retry
- Safety Mode ដើម្បីការពារការ ban
- Verification Code (SMS/Email) ដោយដៃ ឬ ស្វ័យប្រវត្តិ

**បន្ទាប់ពីចុះឈ្មោះ:**
- Backup ទិន្នន័យគណនី (UID, cookies, profile) ដោយស្វ័យប្រវត្តិ
- រក្សាទុកក្នុង `account_backup/` folder

---

## ៣. គណនី (Account Management)

### ផ្ទាំងគណនីសំខាន់
- បង្ហាញបញ្ជីគណនីទាំងអស់ក្នុង table: UID, ឈ្មោះ, អ៊ីមែល, លេខទូរស័ព្ទ, ពាក្យសម្ងាត់, ថ្ងៃខែឆ្នាំ, ភេទ, ឧបករណ៍, ស្ថានភាព
- Filter តាម Category, Status, ឬ Search
- Category ផ្ទាល់ខ្លួន (Custom Categories)
- Context Menu: Copy field, View Details, Delete, Assign Category, Export

### Import / Export
- Import ពី CSV, JSON, ឬ TAR folder (backup folder)
- Export គណនីទៅ CSV
- Preview និង Validate មុន import

### Account Details
- មើលព័ត៌មានលម្អិតគណនី រួមមាន cookies, device info, profile
- Restore session ទៅឧបករណ៍ Android

---

## ៤. Login / Restore Session

- ជ្រើសរើសគណនីពី queue ហើយ restore session ទៅឧបករណ៍
- Batch mode: restore ច្រើនគណនីក្នុងពេលតែមួយ
- ត្រួតពិនិត្យស្ថានភាព login នីមួយៗ
- Submit verification code ដោយដៃ

---

## ៥. ឧបករណ៍ Android (Device Management)

### ការគ្រប់គ្រងឧបករណ៍
- Refresh បញ្ជីឧបករណ៍ដែលភ្ជាប់ (ADB)
- Context Menu លើឧបករណ៍នីមួយៗ:
  - **Screen View** — មើលអេក្រង់ (scrcpy)
  - **Home Screen** — ផ្ញើទៅ Home
  - **Clear Recents** — លុបកម្មវិធីថ្មីៗ
  - **Switch Keyboard** — ប្តូរ keyboard
  - **Set Wallpaper** — កំណត់ wallpaper
  - **Reboot** — restart ឧបករណ៍

### Facebook App
- ដំឡើង / លុប / ដំឡើងឡើងវិញ Facebook Lite ឬ Facebook ដើម
- លុប Cache និងទិន្នន័យ Facebook
- Diagnose screen casting

---

## ៦. Device Spoofer (MaxChange)

ប្រើ MaxChange app ដើម្បីក្លែងបន្លំ device identity:

- ប្តូរ Android ID, Device Model, Build Fingerprint, Serial Number, MAC Address
- ជ្រើសរើស Brand filter (Samsung, Xiaomi, Oppo, ...)
- Random spoof ឬ ជ្រើសរើស brand ជាក់លាក់
- ពិនិត្យ device info បច្ចុប្បន្ន
- Advanced Settings: កំណត់ manual values

---

## ៧. VPN / Proxy

### OpenVPN
- Import VPN profile (.ovpn files) — ម្តងមួយ ឬ ច្រើន
- Push VPN profiles ទៅឧបករណ៍ Android
- Connect VPN — ចៃដន្យ ឬ ជ្រើសរើស server ជាក់លាក់
- Disconnect VPN ពីឧបករណ៍ច្រើន
- Backup / Restore VPN profiles
- Advanced VPN Settings

### Proxy
- Connect Random Proxy
- Connect Specific Proxy
- Disconnect Proxy
- Check Proxy Status

### IP Check
- ពិនិត្យ Local IP, Public IP, ប្រទេស, ទីក្រុង, ISP
- បង្ហាញ Flag emoji

---

## ៨. ភាសា (i18n)

- គាំទ្រ ភាសាខ្មែរ និង English
- ប្តូរភាសាបានភ្លាមៗដោយមិនចាំបាច់ restart
- Font Khmer ស្វ័យប្រវត្តិ

---

## ៩. Settings

- Auto-detect APK path
- Save/Load settings ដោយស្វ័យប្រវត្តិ
- Advanced Config Dialog
- Automation Settings: delay, count, parallel, retry

---

## តម្រូវការប្រព័ន្ធ

| ធាតុ | តម្រូវការ |
|------|-----------|
| OS | Windows 10 / 11 |
| Python | 3.10+ |
| ADB | platform-tools (រួមបញ្ចូលក្នុង folder) |
| Appium | Appium Server (សម្រាប់ auto registration) |
| Android | ឧបករណ៍ភ្ជាប់តាម USB + USB Debugging ON |
| MaxChange | ដំឡើងក្នុងឧបករណ៍ (សម្រាប់ device spoof) |
| OpenVPN | ដំឡើងក្នុងឧបករណ៍ (សម្រាប់ VPN) |

---

## ការដំណើរការ

```bash
python gui.py
```

---

## រចនាសម្ព័ន្ធ Folder

```
├── gui.py                  # កម្មវិធីសំខាន់
├── app.py                  # entry point
├── account_backup/         # ទិន្នន័យ backup គណនី
├── platform-tools/         # ADB tools
├── logo/                   # រូបភាព
└── reg account/            # ទិន្នន័យចុះឈ្មោះ
```
