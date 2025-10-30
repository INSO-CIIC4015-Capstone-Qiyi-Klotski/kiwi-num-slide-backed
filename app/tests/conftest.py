import os, sys
# .../kiwi-num-slide-backed/app/tests -> subir dos niveles hasta la raíz del repo
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
