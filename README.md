# Fury F-Droid Repository

Automated ARM-only F-Droid repository powered by GitHub Actions.

## Features

- **Automated Updates**: Runs every 6 hours via GitHub Actions
- **ARM Only**: Filters out x86/x86_64 builds, keeps only arm64-v8a and armeabi-v7a
- **Signature Pinning**: Prevents silent signing key changes
- **Version Retention**: Configurable number of versions to keep per app
- **Non-blocking CI**: Single app failures don't block the entire repo
- **No APK Storage**: Only metadata is stored, APKs are linked from GitHub Releases

## Repository URL

```
https://untamed-fury.github.io/fury-fdroid-v2
```

Add this to your F-Droid client or Aurora Store.

## Directory Structure

```
.
├── apps.yaml              # App configuration (60+ apps)
├── apps.test.yaml         # Test configuration with minimal apps
├── config.py              # fdroidserver configuration
├── requirements.txt       # Python dependencies
├── main.py                # Simple server entry point
├── serve.py               # Local test server
├── scripts/
│   ├── main.py            # Main orchestrator
│   ├── fetch_releases.py  # GitHub API release fetching
│   ├── asset_selector.py  # APK asset filtering
│   ├── apk_processor.py   # APK metadata extraction (androguard)
│   ├── validator.py       # Validation rules
│   ├── index_builder.py   # index-v2.json builder
│   └── reporter.py        # Error reporting
└── repo/
    ├── index-v2.json      # F-Droid v2 index (generated)
    ├── index-v1.json      # F-Droid v1 index (generated)
    └── icons/             # Repository icons
```

## Local Testing

### Prerequisites

```bash
# Create virtual environment
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip sync requirements.txt
pip install androguard  # For APK parsing
```

### Run the Builder

```bash
# Full build (all 60 apps)
python scripts/main.py

# Test build (minimal apps)
cp apps.test.yaml apps.yaml
python scripts/main.py
```

### Serve Locally

```bash
# Start local server
python serve.py

# Access in browser or F-Droid client
# http://localhost:8080/index-v2.json
```

## GitHub Actions Workflow

The workflow (`.github/workflows/update-repo.yml`) runs:

1. **Schedule**: Every 6 hours (`0 */6 * * *`)
2. **Manual**: Via "Run workflow" button
3. **Push**: When `apps.yaml` or scripts change

### Workflow Steps

1. Checkout repository
2. Set up Python 3.11
3. Install dependencies (including androguard)
4. Run `scripts/main.py` to build index
5. Commit and push changes to `repo/`
6. Upload artifacts

## Configuration

### apps.yaml

```yaml
repo:
  name:
    en-US: Fury F-Droid Repo
  description:
    en-US: Automated ARM-only GitHub-based repository
  url: https://untamed-fury.github.io/fury-fdroid-v2
  max_versions_default: 2

apps:
  - logical_id: myapp
    github: owner/repo
    release:
      prefer_prerelease: false
      include_prerelease_if_no_stable: true
      ignore_drafts: true
    package:
      allowed_ids:
        - com.example.myapp
      allow_pkg_change: false
    abi_policy: arm_preferred  # or arm64_only
    retention:
      retain_versions: 2
    asset_filter:
      exclude_keywords:
        - debug
        - x86
    metadata:
      categories:
        - Internet
      license: GPL-3.0-only
      source_url: https://github.com/owner/repo
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub API token (auto-set in Actions) | - |
| `FDROID_KEYSTORE_PASS` | Keystore password | `android` |
| `FDROID_KEY_PASS` | Key password | `android` |
| `FDROID_KEYSTORE` | Keystore file path | `fdroid.keystore` |
| `FDROID_KEY_ALIAS` | Key alias | `fdroid-repo` |

## Adding New Apps

1. Edit `apps.yaml`
2. Add a new app entry (see format above)
3. Commit and push
4. Workflow runs automatically

## Troubleshooting

### Build Fails

Check the workflow logs in GitHub Actions:
1. Go to repository → Actions
2. Click on failed workflow
3. Check "Run F-Droid builder" step

### No APKs Found

- Check `asset_filter.exclude_keywords` - might be too restrictive
- Verify release has APK assets (not just source code)
- Check if APK filename contains excluded keywords

### Signature Changed Error

This is intentional security. To allow signature changes:
```yaml
signature:
  allow_signature_change: true
```

## License

MIT License - see LICENSE file

## Credits

- [F-Droid](https://f-droid.org/) - Original F-Droid project
- [androguard](https://github.com/androguard/androguard) - APK parsing library
- [xarantolus/fdroid](https://github.com/xarantolus/fdroid) - Inspiration for auto-updating repo
