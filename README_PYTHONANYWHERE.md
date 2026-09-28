# Despliegue en PythonAnywhere

PythonAnywhere sirve Flask con un archivo WSGI que se configura desde la pestaña **Web**. No se usa `app.run()` como servidor público.

## Requisito de almacenamiento

La carpeta actual `static/img/` contiene 84 fotos y ocupa aproximadamente **565 MB**. La base SQLite local ocupa aproximadamente **103 MB**, sin contar el código ni el virtualenv. El plan Beginner incluye 512 MB, así que no alcanza para esta copia completa. Para conservar todas las fotos y la base se necesita, como mínimo, un plan con más almacenamiento (la página de planes consultada lista 5 GB para Developer), o bien reducir/externalizar fotos antes del despliegue.

No borré ni recomprimí las fotos originales. Si se elige un plan de 512 MB, habrá que preparar una selección optimizada y reducir también el tamaño de la base transferida.

## 1. Subir el proyecto

Desde una consola Bash de PythonAnywhere:

```bash
git clone https://github.com/dennisventurah/ichuriverweb.git ~/ichuriverweb
cd ~/ichuriverweb
git lfs install
git lfs pull
```

Si `git lfs` no está instalado en tu cuenta, sube el contenido de `static/img/` desde la pestaña **Files** de PythonAnywhere. El resto del proyecto se obtiene con Git.

## 2. Crear el virtualenv

Elige la versión Python disponible en tu cuenta y úsala también al crear la aplicación Web. Ejemplo con Python 3.13:

```bash
mkvirtualenv --python=/usr/bin/python3.13 ichuriverweb-venv
workon ichuriverweb-venv
pip install -r ~/ichuriverweb/requirements.txt
```

La aplicación necesita `Flask`, `SQLAlchemy`, `numpy`, `rasterio`, `pyproj` y `shapely`. Si la instalación de `rasterio` falla por dependencias nativas, revisa los logs de instalación y los paquetes disponibles para el Python de tu cuenta antes de continuar; el endpoint hipsométrico necesita esos módulos.

## 3. Preparar datos privados

En una Bash console, crea el directorio de datos fuera del código y de los archivos web públicos:

```bash
mkdir -p ~/.local/share/ichuriverweb
chmod 700 ~/.local/share/ichuriverweb
```

Crea `~/.local/share/ichuriverweb/.env` con credenciales propias:

```dotenv
SECRET_KEY=reemplaza-por-un-secreto-aleatorio-largo
ADMIN_USER=admin
ADMIN_PASSWORD=reemplaza-por-una-contrasena-segura
```

No subas este `.env` a GitHub ni lo guardes dentro de `static/` o del directorio público.

La base se ubicará en:

```text
~/.local/share/ichuriverweb/ichu.db
```

Si necesitas mantener los registros existentes, transfiere `ichu.db` local a esa ruta usando la pestaña **Files**. No está en Git porque se excluye mediante `.gitignore`. Conserva el archivo de la base y sus datos; al iniciar, la app aplica las migraciones compatibles.

## 4. Configurar la aplicación Web

1. Abre **Web** en PythonAnywhere y selecciona **Add a new web app**.
2. Elige **Manual configuration** y la misma versión de Python del virtualenv.
3. En **Virtualenv**, configura `/home/TU_USUARIO/.virtualenvs/ichuriverweb-venv`.
4. En **Static files**, agrega el mapping `/static/` a `/home/TU_USUARIO/ichuriverweb/static/`.
5. Abre el archivo WSGI que aparece en la página Web y reemplaza su contenido por `deploy/pythonanywhere/wsgi.py` del repositorio. No dejes literalmente el marcador `YOUR_USERNAME`; el ejemplo usa `Path.home()` y espera que el repo esté en `~/ichuriverweb`.
6. Pulsa **Reload**.

Los endpoints y los templates permanecen gestionados por Flask; solo `/static/` se sirve directamente por PythonAnywhere.

## 5. Verificación

Abre el dominio de PythonAnywhere y comprueba la página inicial, el mapa y el inicio de sesión `/admin/login`. Si aparece un error 500, revisa **Web > Log files > Error log**. Para cambios posteriores, haz `git pull` en Bash y pulsa **Reload** en Web.

PythonAnywhere puede mantener procesos WSGI con código anterior hasta que recargues la aplicación. La base y `.env` quedan fuera del mapeo público.

## Documentación oficial consultada

- [Configurar Flask en PythonAnywhere](https://help.pythonanywhere.com/pages/Flask/)
- [Mapear archivos estáticos](https://help.pythonanywhere.com/pages/StaticFiles/)
- [Planes y almacenamiento](https://www.pythonanywhere.com/pricing/)
