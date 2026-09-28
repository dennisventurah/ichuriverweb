# ichuriverweb

Visualizador de datos meteorológicos e hidrológicos de la cuenca experimental del río Ichu.

## PythonAnywhere

La guía de despliegue está en [README_PYTHONANYWHERE.md](README_PYTHONANYWHERE.md). La configuración WSGI de ejemplo está en `deploy/pythonanywhere/wsgi.py`.

La aplicación guarda SQLite y la clave de sesión en un directorio privado configurado por `ICHU_DATA_DIR`; no coloques la base dentro del mapeo público `/static/`.
