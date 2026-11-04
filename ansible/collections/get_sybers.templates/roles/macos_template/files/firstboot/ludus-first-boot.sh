#!/bin/bash
# Ludus macOS template - first-boot provisioner.
# Injected onto the Data volume from Recovery by the unattended build driver
# and run once by the com.ludus.firstboot LaunchDaemon on the first boot of the
# freshly installed OS. It creates the template's admin user, enables Remote
# Login (SSH) so the build's FINALIZE play can reach the guest, suppresses the
# first-login Setup Assistant for that user, then removes itself.
# __LUDUS_USER__ / __LUDUS_PASS__ are substituted by the driver at build time.
exec >/var/log/ludus-firstboot.log 2>&1
set -x
USERNAME="__LUDUS_USER__"
PASSWORD="__LUDUS_PASS__"

# Wait for OpenDirectory to answer before touching the user database.
for _ in $(seq 1 60); do
  /usr/bin/dscl . -list /Users >/dev/null 2>&1 && break
  /bin/sleep 2
done

# Create the admin user if absent (retry: directory services can still be
# settling on the very first boot).
for _ in $(seq 1 10); do
  if /usr/bin/id "$USERNAME" >/dev/null 2>&1; then break; fi
  /usr/sbin/sysadminctl -addUser "$USERNAME" -fullName "Local User" -password "$PASSWORD" -admin
  /bin/sleep 3
done
/usr/bin/id "$USERNAME" || exit 1

# Remote Login (SSH) for everyone, plus the SSH access group when present.
/bin/launchctl enable system/com.openssh.sshd 2>/dev/null
/bin/launchctl load -w /System/Library/LaunchDaemons/ssh.plist 2>/dev/null
/usr/sbin/systemsetup -setremotelogin on 2>/dev/null
/usr/sbin/dseditgroup -o edit -a "$USERNAME" -t user com.apple.access_ssh 2>/dev/null || true

# Never show Setup Assistant: system-wide and for the new user's first login.
/usr/bin/touch /var/db/.AppleSetupDone
/usr/bin/touch /private/var/db/.AppleSetupDone 2>/dev/null
HOME_DIR="/Users/$USERNAME"
/bin/mkdir -p "$HOME_DIR/Library/Preferences"
PREF="$HOME_DIR/Library/Preferences/com.apple.SetupAssistant"
for key in DidSeeCloudSetup DidSeePrivacy DidSeeSiriSetup DidSeeAppearanceSetup DidSeeTouchIDSetup \
  DidSeeActivationLock DidSeeScreenTime DidSeeAccessibility DidSeeTrueTonePrivacy DidSeeSyncSetup \
  DidSeeSyncSetup2 DidSeeiCloudLoginForStorageServices DidSeeAvatarSetup; do
  /usr/bin/defaults write "$PREF" "$key" -bool true
done
/usr/bin/defaults write "$PREF" LastSeenCloudProductVersion -string "$(/usr/bin/sw_vers -productVersion)"
/usr/bin/defaults write "$PREF" LastSeenBuddyBuildVersion -string "$(/usr/bin/sw_vers -buildVersion)"
/usr/sbin/chown "$USERNAME" "$HOME_DIR/Library" "$HOME_DIR/Library/Preferences" "$PREF.plist" 2>/dev/null || true

# Self-destruct: this must only ever run once.
/bin/rm -f /Library/LaunchDaemons/com.ludus.firstboot.plist
/bin/rm -f /usr/local/bin/ludus-first-boot.sh
exit 0
