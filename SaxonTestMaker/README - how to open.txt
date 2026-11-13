SAXON TEST MAKER
================

MAC
---
1. Unzip the folder anywhere (Desktop, Documents, ...). Keep all the files together.
2. First time only - macOS blocks downloaded scripts:
     Right-click "SETUP (run once).command"  ->  Open  ->  Open again in the dialog.
   That fixes permissions, then starts the Test Maker for you.
3. After that, just double-click:  Saxon Test Maker.command
   Your default browser opens with the portal. Leave the Terminal window open while you use it.

   If you see "do not have appropriate access privileges", open Terminal, drag the folder in, and run:
       chmod +x "Saxon Test Maker.command"
       xattr -d com.apple.quarantine "Saxon Test Maker.command"

WINDOWS
-------
Double-click  Saxon Test Maker.bat   (SmartScreen: More info -> Run anyway).
Needs Python 3 (python.org; tick "Add python.exe to PATH" when installing).

USING IT
--------
- Filter/pick problems (or "Pick random from view"), set Title, Test # (shows as 22A / 22B), Forms (A,B,C...), Seed.
- "Generate test" opens a new tab: Test A, Key A, Test B, Key B ... one page each.
- About 15-20 problems fit on a page. The type size and spacing adjust automatically in the browser;
  a yellow notice appears if there are too many to fit.
- Print: Ctrl/Cmd+P -> "Save as PDF" (or your printer). Paper: Letter. Margins: Default.
  Turn ON "Background graphics" so the gray TEST bar prints. Turn OFF "Headers and footers".
- Same seed + same problems = same test. Change the seed for a fresh set.
