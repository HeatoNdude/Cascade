import json
import urllib.request
import sys
import subprocess
import os

print("Fetching latest releases from jllllll/llama-cpp-python-cuBLAS-wheels...")
url = "https://api.github.com/repos/jllllll/llama-cpp-python-cuBLAS-wheels/releases"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        releases = json.loads(response.read().decode())
except Exception as e:
    print(f"Failed to fetch releases: {e}")
    sys.exit(1)

# Find highest version wheel for cp311, win_amd64, cu122/cu124
target_wheel_url = None
for release in releases:
    for asset in release.get('assets', []):
        name = asset.get('name', '')
        if 'cp311' in name and 'win_amd64' in name and ('cu122' in name or 'cu124' in name or 'cu121' in name) and name.endswith('.whl'):
            if 'tensorcores' not in name: # Prefer standard build if possible, though tensorcores is fine too
                target_wheel_url = asset.get('browser_download_url')
                print(f"Found match: {name}")
                break
    if target_wheel_url:
        break

if not target_wheel_url:
    print("Could not find a compatible pre-built `.whl` file.")
    sys.exit(1)

wheel_filename = target_wheel_url.split('/')[-1]
wheel_path = os.path.join(os.getcwd(), wheel_filename)

print(f"Downloading {wheel_filename}...")
urllib.request.urlretrieve(target_wheel_url, wheel_path)

print("Installing downloaded wheel...")
pip_exe = os.path.join(os.getcwd(), ".venv", "Scripts", "pip.exe")
subprocess.check_call([pip_exe, "install", wheel_path, "--force-reinstall", "--no-cache-dir"])

print("Successfully installed pre-compiled CUDA wheel!")
