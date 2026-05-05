# FRT Source Package Structure

```
src/
├── core/                       # App-wide infrastructure
│   ├── config.py               # Load / save JSON settings (frt_config.json)
│   ├── constants.py            # App-wide constants (package names, defaults)
│   └── subprocess_utils.py     # Windows-safe subprocess wrapper + global patch
│
├── i18n/                       # Internationalisation
│   ├── translations.py         # All string translations (EN / Khmer / VI)
│   └── engine.py               # _T(), _reg(), apply_language(), font loader
│
├── automation/                 # Android automation logic
│   ├── registration.py         # FacebookRegistration — Appium-driven signup flow
│   └── url_normalizer.py       # normalize_facebook_url() + URL_TYPE_LABELS
│
├── workers/                    # Background QThread workers
│   ├── device_worker.py        # DeviceWorker  — ADB device list + info
│   └── maxchange_worker.py     # MaxChangeWorker — device spoofing
│
├── utils/                      # Stateless helper utilities
│   ├── adb.py                  # run_adb(), get_device_prop(), list_connected_devices()
│   ├── account_backup.py       # find_account_folders(), parse_acc_info()
│   └── name_generator.py       # random_full_name(), generate_name_list()
│
└── ui/                         # PyQt6 user interface
    ├── styles.py               # DARK_STYLE global stylesheet
    ├── widgets.py              # LogSignal, RingChartWidget
    ├── main_window.py          # MainWindow (re-exports from gui.py during migration)
    ├── tabs/                   # One file per tab (populated as gui.py is split)
    │   └── __init__.py
    └── dialogs/                # One file per dialog (populated as gui.py is split)
        └── __init__.py
```

## Entry point

`main.py` at the project root — replaces `gui.py` as the launch target.

## Migration status

`gui.py` is the legacy monolith (~24 k lines).  
The modules above are the clean replacements.  
`src/ui/main_window.py` currently re-exports `MainWindow` from `gui.py`
so the app runs unchanged while the migration continues tab-by-tab.

## Adding a new language

1. Open `src/i18n/translations.py`
2. Add a new top-level key to `TRANSLATIONS` (copy the `"EN"` block as a template)
3. The language selector in Settings will pick it up automatically

## Adding a new tab

1. Create `src/ui/tabs/my_tab.py` with a `build_my_tab(window) -> QWidget` function
2. Call it from `MainWindow.init_ui()` and add it to the tab widget
