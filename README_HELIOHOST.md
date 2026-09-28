# Desplegar en HelioHost

HelioHost ejecuta Flask mediante WSGI. Esta configuración publica la app en la raíz del dominio y mantiene el código fuente y SQLite fuera de `httpdocs`.

## 1. Estructura del servidor

En Plesk/File Manager o por SFTP, prepara estas rutas (reemplaza `<usuario>`):

```text
/home/<usuario>/ichu_app/       # clon/copia completa del repositorio
/home/<usuario>/ichu_data/      # SQLite, clave de sesión y .env; fuera de httpdocs
/home/<usuario>/httpdocs/       # webroot del dominio
```

Sube el repositorio completo a `ichu_app`, incluyendo `data/`, `models/`, `templates/` y `static/`. No subas el directorio `instance/` local.

Copia `deploy/heliohost/.htaccess` y `deploy/heliohost/flask.wsgi` a `httpdocs/`. Edita las dos rutas `APP_ROOT` y `PRIVATE_DATA_DIR` en `flask.wsgi` con el usuario real de HelioHost.

Si ya existe un `index.html`, `index.php` u otro índice en `httpdocs`, renómbralo o retíralo para que no tome prioridad sobre las reglas WSGI.

## 2. Variables y base de datos

Crea `/home/<usuario>/ichu_data/.env` (no dentro de `httpdocs`) con valores privados:

```dotenv
SECRET_KEY=una-clave-aleatoria-larga
ADMIN_USER=admin
ADMIN_PASSWORD=una-clave-administrativa-segura
```

`flask.wsgi` carga este archivo antes de importar la aplicación. La base se crea en:

```text
/home/<usuario>/ichu_data/ichu.db
```

Si necesitas conservar una base local ya poblada, transfiere `ichu.db` por SFTP a esa ruta antes de iniciar la web. No la coloques en `httpdocs`. El proceso WSGI debe poder escribir en `ichu_data`.

## 3. Dependencias

HelioHost ofrece Flask/WSGI en sus servidores Plesk. Verifica en la página oficial de módulos instalados de tu servidor que estén disponibles `SQLAlchemy`, `numpy`, `rasterio`, `pyproj` y `shapely`. La aplicación usa `rasterio`, `pyproj` y `shapely` para los cálculos geomorfológicos; si falta alguno, consulta con soporte de HelioHost para la versión de Python de tu servidor antes de activar el sitio.

Las dependencias requeridas se enumeran en `requirements.txt`. HelioHost puede no permitir instalar paquetes nativos arbitrarios en cuentas compartidas.

## 4. Activación

El archivo `.htaccess` enruta las solicitudes al `flask.wsgi`; la aplicación expone páginas, API y archivos estáticos desde Flask. Abre el dominio y revisa los logs de errores de Plesk si aparece un error 500.

HelioHost indica que WSGI puede mantener código cacheado durante un máximo aproximado de dos horas en Tommy/Johnny. Los cambios pueden tardar en reflejarse. Las fotos de estaciones están incluidas bajo `static/img/<CODIGO_ESTACION>/`.

## Documentación oficial

- [Flask en HelioHost](https://wiki.helionet.org/Flask)
- [Python en HelioHost](https://wiki.helionet.org/Python_Tutorial)
- [SQLite en HelioHost](https://wiki.helionet.org/SQLite)
- [Subir archivos por SFTP](https://wiki.helionet.org/Uploading_Files)
