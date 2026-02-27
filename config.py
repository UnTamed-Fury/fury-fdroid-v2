"""
F-Droid repository configuration.

This file is used by fdroidserver tools.
For our custom builder, configuration is in apps.yaml.
"""

import os

# Repository information
repo_url = os.environ.get('FDROID_REPO_URL', 'https://untamed-fury.github.io/fury-fdroid-v2')
repo_name = 'Fury F-Droid Repo'
repo_description = 'Automated ARM-only GitHub-based repository for Android apps'

# Signing configuration (for fdroidserver)
# These are defaults - override with environment variables in CI
keystorepass = os.environ.get('FDROID_KEYSTORE_PASS', 'android')
keypass = os.environ.get('FDROID_KEY_PASS', 'android')
keystore = os.environ.get('FDROID_KEYSTORE', 'fdroid.keystore')
repo_keyalias = os.environ.get('FDROID_KEY_ALIAS', 'fdroid-repo')

# Repository settings
max_versions = 2
keep_max_apks = 2

# Only include ARM builds
preferred_abis = ['arm64-v8a', 'armeabi-v7a']

# Disable x86 builds
disable_x86 = True
