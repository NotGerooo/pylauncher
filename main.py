import sys
import os

# 1. Fix directorio de trabajo para PyInstaller .exe
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# 2. Fix sys.path ANTES de cualquier import del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 3. Fix SSL ANTES de cualquier import de red (urllib, etc.)
if getattr(sys, 'frozen', False):
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
else:
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context

# 4. Ahora sí importar el proyecto
from utils.logger import setup_logger
from gui.app import App


def main():
    setup_logger()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()