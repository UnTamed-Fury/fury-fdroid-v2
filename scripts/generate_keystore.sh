#!/bin/bash
# Generate a keystore for signing the F-Droid repository
# This is ONLY for the repo metadata, NOT for signing APKs

set -e

KEYSTORE_FILE="repo/fdroid.keystore"
KEYSTORE_PASS="android"
KEY_PASS="android"
KEY_ALIAS="fdroid-repo"
VALIDITY_DAYS="3650"

echo "=== F-Droid Repository Keystore Generator ==="
echo ""

if [ -f "$KEYSTORE_FILE" ]; then
    echo "WARNING: Keystore already exists at $KEYSTORE_FILE"
    echo "Delete it first if you want to generate a new one"
    exit 1
fi

echo "Generating new keystore..."
echo "  - File: $KEYSTORE_FILE"
echo "  - Alias: $KEY_ALIAS"
echo "  - Validity: $VALIDITY_DAYS days"
echo ""

# Generate keystore using keytool
keytool -genkey -v \
    -keystore "$KEYSTORE_FILE" \
    -alias "$KEY_ALIAS" \
    -keyalg RSA \
    -keysize 2048 \
    -validity $VALIDITY_DAYS \
    -storepass "$KEYSTORE_PASS" \
    -keypass "$KEY_PASS" \
    -dname "CN=Fury F-Droid Repo, OU=Fury, O=Fury, L=Unknown, ST=Unknown, C=US"

echo ""
echo "=== Keystore generated successfully ==="
echo ""
echo "IMPORTANT: Store these credentials securely:"
echo "  - Keystore file: $KEYSTORE_FILE"
echo "  - Keystore password: $KEYSTORE_PASS"
echo "  - Key password: $KEY_PASS"
echo "  - Key alias: $KEY_ALIAS"
echo ""
echo "Add them to config.py or environment variables"
