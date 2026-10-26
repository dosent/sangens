"""Сборка разового помощника для текущего Mac без сторонних зависимостей."""
from pathlib import Path
import plistlib
import platform
import shutil
import subprocess
import sys

source = Path(__file__).resolve().parent
output = Path(sys.argv[1]).resolve()
app = output / 'Sangens Setup.app'
contents = app / 'Contents'
(contents / 'MacOS').mkdir(parents=True, exist_ok=True)
(contents / 'Resources').mkdir(exist_ok=True)
subprocess.run(['swiftc', '-target', f'{platform.machine()}-apple-macosx13.0', '-module-cache-path', str(output / '.swift-module-cache'),
                str(source / 'VerificationState.swift'), str(source / 'main.swift'),
                '-framework', 'AppKit', '-framework', 'WebKit',
                '-o', str(contents / 'MacOS' / 'SangensSetup')], check=True)
shutil.copyfile(source / 'captcha.html', contents / 'Resources' / 'captcha.html')
with (contents / 'Info.plist').open('wb') as target:
    plistlib.dump({'CFBundleIdentifier':'local.sangens.ha.setup', 'CFBundleName':'Sangens Setup',
                  'CFBundleDisplayName':'Sangens — настройка HA', 'CFBundleExecutable':'SangensSetup',
                  'CFBundlePackageType':'APPL', 'CFBundleVersion':'1', 'CFBundleShortVersionString':'0.3.0',
                  'LSMinimumSystemVersion':'13.0', 'NSHighResolutionCapable':True}, target)
print(app)
