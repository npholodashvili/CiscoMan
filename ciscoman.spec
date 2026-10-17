# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CiscoMan Windows desktop application."""

import sys
from pathlib import Path

block_cipher = None

# Collect ntc-templates data files
ntc_templates_path = None
try:
    import ntc_templates
    ntc_templates_path = Path(ntc_templates.__file__).parent
except ImportError:
    pass

datas = []
if ntc_templates_path:
    datas.append((str(ntc_templates_path / 'templates'), 'ntc_templates/templates'))

# Include OUI database
oui_db_path = Path('ciscoman_core/oui.db')
if oui_db_path.exists():
    datas.append((str(oui_db_path), 'ciscoman_core'))
    datas.append((str(oui_db_path), '.'))

icon_path = Path('ciscoman_gui/icon.ico')
if icon_path.exists():
    datas.append((str(icon_path), 'ciscoman_gui'))

a = Analysis(
    ['ciscoman_gui/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'ciscoman_core',
        'ciscoman_core.actions',
        'ciscoman_core.database',
        'ciscoman_core.config',
        'ciscoman_core.network_utils',
        'ciscoman_core.simulator',
        'ciscoman_core.wizard',
        'ciscoman_core.cheatsheet',
        'ciscoman_core.tunnel_wizard',
        'ciscoman_core.port_panel',
        'ciscoman_core.input_validation',
        'ciscoman_core.ssh_hostkeys',
        'ciscoman_core.mac_discovery',
        'ciscoman_core.snmp_discovery',
        'ciscoman_core.snmpv2c',
        'ciscoman_core.fingerprint',
        'ciscoman_core.switch_arp',
        'ciscoman_core.selftest',
        'ciscoman_core.device_identification',
        'ciscoman_core.win_native',
        'ciscoman_gui.theme',
        'ciscoman_gui.crash_guard',
        'ciscoman_gui.workers',
        'shiboken6',
        'ntc_templates.parse',
        'textfsm',
        'keyring',
        'keyring.backends.Windows',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tk',
        'tkinter',
        '_tkinter',
        'PIL',
        'streamlit',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CiscoMan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ciscoman_gui/icon.ico' if Path('ciscoman_gui/icon.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CiscoMan',
)
