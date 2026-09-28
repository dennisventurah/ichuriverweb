# ichuriverweb

Visualizador de datos meteorológicos e hidrológicos de la cuenca experimental del río Ichu.

## HelioHost

La guía de instalación está en [README_HELIOHOST.md](README_HELIOHOST.md). Esta aplicación usa Flask mediante el WSGI de Plesk y almacena SQLite en un directorio privado configurado por `ICHU_DATA_DIR`.

Antes de activarla, verifica que tu servidor tenga `SQLAlchemy`, `numpy`, `rasterio`, `pyproj` y `shapely`. HelioHost puede requerir que solicites módulos de Python nativos que no estén disponibles en el servidor.
