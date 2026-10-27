# Getting the Windows program (HYSalesEngine.exe)

## Quickest: just run it (no .exe needed)
Install **Python 3.12** from python.org (tick **Add Python to PATH**), then double-click **start.bat** in the main folder.
The first run sets itself up, then your browser opens. Next time, double-click it again.
**Use Python 3.12 or 3.11.** The very newest Python (3.14) can fail while installing packages.
If an earlier attempt failed, start.bat repairs itself. If it still fails, delete the `backend\.venv` folder and try again.


I could not build the .exe myself, because the tools I work in are not Windows. The build recipe is in this folder,
and I ran the same recipe here as a Linux program and checked it (see README). On Windows it takes one double-click.
Pick one way:

## Way 1: build it on your own PC (needs Python and Node, once)
1. Install **Python 3.12** from python.org. Tick **Add Python to PATH**. (If you have several Pythons, the script picks 3.12 first.)
2. Install **Node.js 18 or newer** from nodejs.org.
3. Optional, for a proper installer: install **Inno Setup 6** from jrsoftware.org.
4. Unzip this project and double-click **build_windows.bat**. It takes a few minutes.

You get:
- `dist\HYSalesEngine\HYSalesEngine.exe` (copy the whole HYSalesEngine folder anywhere), and
- `installer\Output\HYSalesEngine-Setup.exe` if Inno Setup was installed.

You do not need Node.js. The screens are already built in `backend\ui`, and the script uses them. (To rebuild the screens yourself, run `build_windows.bat rebuild`. If that fails with an SWC error, delete the `frontend\node_modules` folder and try again.)

## Way 2: let GitHub build it, nothing to install
1. Create a **private** GitHub repository and upload this project.
2. Open the **Actions** tab, choose **Build Windows app**, press **Run workflow**.
3. When it finishes, download **HYSalesEngine-Setup** from the run. (I could not run this workflow myself.)

## Using it
Run the installer (or HYSalesEngine.exe). A black window opens and your browser shows the program.
**Leave the black window open**: closing it stops calls and follow-ups. Next time, start it from the Start menu or desktop icon.

## Good to know
- Windows may show a blue "Windows protected your PC" screen, and antivirus tools sometimes flag new programs
  built this way. The program is not digitally signed. Choose "More info", then "Run anyway", and
  if your antivirus complains, add the HYSalesEngine folder to its allowed list.
- Updating: install the new version over the old one. Your data stays.
- Your data lives in `%APPDATA%\HYSalesEngine` (type that in the Windows address bar). Back up this whole folder.
