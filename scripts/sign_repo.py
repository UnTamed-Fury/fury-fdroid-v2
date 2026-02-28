#!/usr/bin/env python3
"""Sign F-Droid repository index files - creates GPG signature and JAR."""

import json
import os
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

def sign_with_gpg(input_file: str, output_sig: str, key_id: str) -> bool:
    """Sign a file with GPG."""
    try:
        result = subprocess.run(
            ['gpg', '--batch', '--yes', '--armor', '--detach-sign',
             '--local-user', key_id, '--output', output_sig, input_file],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"GPG signing failed: {e}")
        return False

def create_index_v1_from_v2(v2_data: dict) -> dict:
    """Convert index-v2.json to index-v1.json format."""
    v1 = {'repo': {}, 'apps': [], 'packages': []}
    repo = v2_data.get('repo', {})
    v1['repo'] = {
        'name': repo.get('name', {}).get('en-US', 'F-Droid Repo'),
        'description': repo.get('description', {}).get('en-US', ''),
        'address': repo.get('address', ''),
        'timestamp': repo.get('timestamp', 0),
    }
    packages = v2_data.get('packages', {})
    for pkg_id, pkg_data in packages.items():
        v1['apps'].append(pkg_id)
        metadata = pkg_data.get('metadata', {})
        versions = pkg_data.get('versions', {})
        for apk_hash, version_data in versions.items():
            manifest = version_data.get('manifest', {})
            file_info = version_data.get('file', {})
            pkg_entry = {
                'packageName': pkg_id,
                'versionName': manifest.get('versionName', ''),
                'versionCode': manifest.get('versionCode', 0),
                'size': file_info.get('size', 0),
                'hash': apk_hash,
                'hashType': 'sha256',
            }
            uses_sdk = manifest.get('usesSdk', {})
            if uses_sdk.get('minSdkVersion'):
                pkg_entry['minSdkVersion'] = uses_sdk['minSdkVersion']
            if uses_sdk.get('targetSdkVersion'):
                pkg_entry['targetSdkVersion'] = uses_sdk['targetSdkVersion']
            if manifest.get('nativecode'):
                pkg_entry['nativecode'] = manifest['nativecode']
            v1['packages'].append(pkg_entry)
    return v1

def create_jar(json_data: dict, jar_path: str) -> bool:
    """Create JAR containing index-v1.json."""
    import tempfile
    import shutil
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            json_path = tmpdir / 'index-v1.json'
            jar_tmp = tmpdir / 'index-v1.jar'
            with open(json_path, 'w') as f:
                json.dump(json_data, f, separators=(',', ':'))
            with zipfile.ZipFile(jar_tmp, 'w', zipfile.ZIP_DEFLATED) as jar:
                jar.write(json_path, 'index-v1.json')
            shutil.copy(jar_tmp, jar_path)
            return True
    except Exception as e:
        print(f"JAR creation failed: {e}")
        return False

def main():
    repo_dir = Path(__file__).parent.parent / 'repo'
    index_v2 = repo_dir / 'index-v2.json'
    if not index_v2.exists():
        print(f"Error: {index_v2} not found")
        return 1
    with open(index_v2) as f:
        v2_data = json.load(f)
    print("Signing index-v2.json...")
    gpg_key = os.environ.get('FDROID_GPG_KEY', 'fury@untamedfury.space')
    if sign_with_gpg(str(index_v2), str(repo_dir / 'index-v2.json.asc'), gpg_key):
        print("Created index-v2.json.asc")
    else:
        print("GPG signing skipped (no key)")
    print("Creating index-v1.json...")
    v1_data = create_index_v1_from_v2(v2_data)
    with open(repo_dir / 'index-v1.json', 'w') as f:
        json.dump(v1_data, f, separators=(',', ':'))
    print("Created index-v1.json")
    print("Creating index-v1.jar...")
    if create_jar(v1_data, str(repo_dir / 'index-v1.jar')):
        print("Created index-v1.jar")
    print("\nDone!")
    return 0

if __name__ == '__main__':
    exit(main())
