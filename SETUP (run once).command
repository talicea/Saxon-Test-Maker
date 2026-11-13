#!/bin/bash
# Run this once after unzipping. It makes the main launcher double-clickable
# for any user on this Mac, then opens the Test Maker.

cd "$(dirname "$0")" || exit 1

echo "Setting permissions…"
chmod +x "Saxon Test Maker.command" "SETUP (run once).command" "saxon_portal.py" "saxon_test.py" 2>/dev/null

# Clear any macOS quarantine flag that blocks downloaded scripts
xattr -d com.apple.quarantine "Saxon Test Maker.command" 2>/dev/null
xattr -d com.apple.quarantine "SETUP (run once).command" 2>/dev/null
xattr -d com.apple.quarantine "saxon_portal.py" 2>/dev/null
xattr -d com.apple.quarantine "saxon_test.py" 2>/dev/null
xattr -cr . 2>/dev/null

echo "Done."
echo ""
echo "You can now double-click:"
echo "  Saxon Test Maker.command"
echo ""
echo "Starting it now…"
echo ""

open "Saxon Test Maker.command"
