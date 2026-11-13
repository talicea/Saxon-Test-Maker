#!/bin/bash
# Saxon Test Maker — double-click to open in your default browser.
# Works for any user account on this Mac.

# Always run from the folder that contains this script
# Ensure node/python from common install locations are visible (GUI apps get a minimal PATH)
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

cd "$(dirname "$0")" || {
  osascript -e 'display dialog "Could not find the Saxon Test Maker folder." buttons {"OK"} default button 1 with icon stop' >/dev/null 2>&1
  exit 1
}

# Make sure this launcher stays executable (zip downloads often lose the +x bit)
chmod u+x "$0" 2>/dev/null
chmod u+x "saxon_portal.py" "saxon_test.py" 2>/dev/null

# Prefer python3; fall back to the python that is actually Python 3
PY=""
if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1 && python -c 'import sys; exit(0 if sys.version_info[0] >= 3 else 1)' 2>/dev/null; then
  PY="python"
fi

if [ -z "$PY" ]; then
  osascript -e 'display dialog "Python 3 is required.

macOS will offer to install the Command Line Tools when you click OK.
After they finish installing, double-click this file again." buttons {"OK"} default button 1 with icon caution' >/dev/null 2>&1
  # Trigger the CLT install prompt
  xcode-select --install 2>/dev/null
  exit 1
fi

# Keep the Terminal window open with a clear message
clear 2>/dev/null
echo "Saxon Test Maker"
echo "----------------"
echo "Starting local portal…"
echo "Your default browser will open in a moment."
echo ""
echo "Leave this Terminal window open while you use the portal."
echo "Close the window (or press Ctrl+C) when you are finished."
echo ""

# Run the portal (it opens the default browser via webbrowser.open)
exec "$PY" saxon_portal.py
