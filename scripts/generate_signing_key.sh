#!/bin/bash
# Generate GPG signing key for F-Droid repository

cat > /tmp/gpg_batch << 'EOF'
%echo Generating F-Droid repo signing key
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: Fury F-Droid Repo
Name-Email: fury@untamedfury.space
Expire-Date: 0
%no-protection
%commit
%echo Done
EOF

gpg --batch --gen-key /tmp/gpg_batch 2>&1

# Export public key
gpg --armor --export fury@untamedfury.space > repo/fdroid-repo.pub

# Show fingerprint
echo "=== PUBLIC KEY FINGERPRINT ==="
gpg --fingerprint fury@untamedfury.space

echo "=== SAVE THIS FINGERPRINT FOR FDROID CLIENT ==="
