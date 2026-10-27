# PyInstaller recipe. Build with:  python -m PyInstaller --noconfirm HYSalesEngine.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hidden = (collect_submodules("uvicorn") + collect_submodules("anyio") + collect_submodules("sqlalchemy.dialects.sqlite")
          + ["pymysql", "multipart", "python_multipart", "openpyxl", "lxml.etree", "lxml._elementpath", "zoneinfo"])
datas = [("ui", "ui")] + collect_data_files("tzdata") + collect_data_files("certifi")

a = Analysis(["launcher.py"], pathex=["."], datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy", "PIL"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="HYSalesEngine", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="HYSalesEngine")
