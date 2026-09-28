from datetime import datetime
from collections import defaultdict
import csv
import json
import os
from pathlib import Path
from functools import lru_cache
from urllib.parse import quote

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import Session, joinedload
from werkzeug.security import check_password_hash, generate_password_hash
from config import Config
from models import Base, Basin, HydrologicalData, MeteorologicalData, Station


app = Flask(__name__)
app.config.from_object(Config)

engine = create_engine(
    app.config['SQLALCHEMY_DATABASE_URI'],
    future=True,
    connect_args={'timeout': 30},
    pool_pre_ping=True,
)


@event.listens_for(engine, 'connect')
def configure_sqlite_connection(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA busy_timeout=30000')
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA synchronous=NORMAL')
    cursor.execute('PRAGMA cache_size=-64000')
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()


def initialize_database():
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        columns = connection.execute(
            text("PRAGMA table_info('datos_meteorologico')")
        ).mappings().all()
        not_nullable = {
            column['name'] for column in columns if column['notnull']
        }
        nullable_columns = {
            'precipitacion', 'temperatura', 'humedad_relativa'
        }
        if not_nullable.intersection(nullable_columns):
            connection.execute(text(
                'DROP INDEX IF EXISTS ix_datos_meteorologico_estacion_id'
            ))
            connection.execute(text(
                'DROP INDEX IF EXISTS ix_datos_meteorologico_fecha_hora'
            ))
            connection.execute(text(
                'ALTER TABLE datos_meteorologico '
                'RENAME TO datos_meteorologico_legacy'
            ))
            Base.metadata.tables['datos_meteorologico'].create(connection)
            connection.execute(text(
                'INSERT INTO datos_meteorologico '
                '(id, estacion_id, fecha_hora, precipitacion, temperatura, humedad_relativa) '
                'SELECT id, estacion_id, fecha_hora, precipitacion, temperatura, humedad_relativa '
                'FROM datos_meteorologico_legacy'
            ))
            connection.execute(text('DROP TABLE datos_meteorologico_legacy'))

        basin_columns = connection.execute(
            text("PRAGMA table_info('cuencas')")
        ).mappings().all()
        existing_columns = {column['name'] for column in basin_columns}
        basin_table = Base.metadata.tables['cuencas']
        for column in basin_table.columns:
            if column.name not in existing_columns:
                connection.execute(text(
                    f'ALTER TABLE cuencas ADD COLUMN {column.name} FLOAT'
                ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS ix_datos_hidrologico_estacion_fecha '
            'ON datos_hidrologico (estacion_id, fecha_hora)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS ix_datos_meteorologico_estacion_fecha '
            'ON datos_meteorologico (estacion_id, fecha_hora)'
        ))


initialize_database()
GEOJSON_PATH = Path(app.root_path) / 'data' / 'cuenca_ichu.geojson'
RASTER_PATH = Path(app.root_path) / 'data' / 'cuenca_ichu.tif'
IMAGES_PATH = Path(app.root_path) / 'static' / 'img'
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD) if ADMIN_PASSWORD else None


@lru_cache(maxsize=1)
def load_geojson():
    with GEOJSON_PATH.open(encoding='utf-8') as geojson_file:
        return json.load(geojson_file)


def parse_date(value, field_name):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError as error:
        raise ValueError(f'{field_name} debe tener formato YYYY-MM-DD') from error


def series_date(value):
    """Devuelve siempre una etiqueta de día compatible con el gráfico."""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    return str(value)[:10]


def rounded_value(value):
    return round(value, 3) if value is not None else None


def calculate_basin_parameters():
    import numpy as np
    import rasterio
    from pyproj import Transformer
    from rasterio.mask import mask
    from rasterio.warp import transform_geom
    from shapely.geometry import shape
    from shapely.ops import transform as transform_shape

    geojson = load_geojson()
    if not geojson.get('features'):
        return {}

    geometry = geojson['features'][0]['geometry']
    with rasterio.open(RASTER_PATH) as raster:
        raster_geometry = transform_geom('EPSG:4326', raster.crs, geometry, precision=2)
        clipped, transform = mask(raster, [raster_geometry], crop=True, filled=False)
        elevations = clipped[0].compressed().astype(float)
        elevations = elevations[elevations > 0]
        pixel_size_x, pixel_size_y = raster.res
        dem = np.ma.asarray(clipped[0], dtype=float).filled(np.nan)
        dem[dem <= 0] = np.nan

    basin_shape = shape(geometry)
    to_metric = Transformer.from_crs('EPSG:4326', 'EPSG:32718', always_xy=True).transform
    metric_shape = transform_shape(to_metric, basin_shape)
    area_km2 = metric_shape.area / 1_000_000
    perimeter_km = metric_shape.length / 1_000
    min_x, min_y, max_x, max_y = metric_shape.bounds
    length_km = ((max_x - min_x) ** 2 + (max_y - min_y) ** 2) ** 0.5 / 1_000
    mean_elevation = float(elevations.mean())
    minimum = float(elevations.min())
    maximum = float(elevations.max())
    relief = maximum - minimum
    slope_y, slope_x = np.gradient(dem, pixel_size_y, pixel_size_x)
    slope_degrees = np.degrees(np.arctan(np.sqrt(slope_x ** 2 + slope_y ** 2)))
    valid_slope = slope_degrees[~np.isnan(slope_degrees)]
    equivalent_diameter = 2 * (area_km2 * 1_000_000 / np.pi) ** 0.5
    return {
        'area_km2': round(area_km2, 3),
        'perimetro_km': round(perimeter_km, 3),
        'longitud_cuenca_km': round(length_km, 3),
        'factor_forma': round(area_km2 / (length_km ** 2), 4) if length_km else None,
        'coeficiente_gravelius': round(perimeter_km / (2 * np.sqrt(np.pi * area_km2)), 4) if area_km2 else None,
        'relacion_elongacion': round(equivalent_diameter / (length_km * 1_000), 4) if length_km else None,
        'relacion_circularidad': round(4 * np.pi * area_km2 / (perimeter_km ** 2), 4) if perimeter_km else None,
        'elevacion_minima': round(minimum, 1),
        'elevacion_maxima': round(maximum, 1),
        'elevacion_media': round(mean_elevation, 1),
        'relieve_total_m': round(relief, 1),
        'pendiente_minima': round(float(valid_slope.min()), 3),
        'pendiente_maxima': round(float(valid_slope.max()), 3),
        'pendiente_media': round(float(valid_slope.mean()), 3),
        'integral_hipsometrica': round(float((elevations - minimum).mean() / relief), 4) if relief else None,
    }


def update_basin_parameters():
    with Session(engine) as session:
        basin_rows = session.scalars(select(Basin)).all()
        if len(basin_rows) != 1:
            return
        basin = basin_rows[0]
        basin_id = basin.id
        calculated_fields = (
            'longitud_cuenca_km', 'factor_forma', 'coeficiente_gravelius',
            'relacion_elongacion', 'relacion_circularidad', 'relieve_total_m',
            'pendiente_minima', 'pendiente_maxima', 'integral_hipsometrica'
        )
        if all(getattr(basin, field) is not None for field in calculated_fields):
            return

    try:
        parameters = calculate_basin_parameters()
    except ImportError:
        return
    if not parameters:
        return
    with Session(engine) as session:
        basin = session.scalar(select(Basin).where(Basin.id == basin_id))
        for key, value in parameters.items():
            setattr(basin, key, value)
        session.commit()


update_basin_parameters()


def precipitation_series(rows, granularity):
    """Agrega lluvia por intervalos a días y después a meses o años."""
    daily_totals = defaultdict(float)
    for timestamp, value in rows:
        if timestamp is not None and value is not None:
            daily_totals[timestamp.strftime('%Y-%m-%d')] += float(value)

    periods = defaultdict(list)
    for day, total in daily_totals.items():
        if granularity == 'year':
            period = day[:4]
        elif granularity == 'month':
            period = day[:7]
        else:
            period = day
        periods[period].append(total)

    return [
        {
            'fecha': period,
            'minimo': rounded_value(min(daily_values)),
            'maximo': rounded_value(max(daily_values)),
            'media': rounded_value(sum(daily_values) / len(daily_values)),
            'valor': rounded_value(sum(daily_values)),
        }
        for period, daily_values in sorted(periods.items())
    ]


def station_to_dict(station):
    latitude = station.latitud
    longitude = station.longitud
    coordinates_are_inverted = (
        -85 <= latitude <= -65 and -20 <= longitude <= 0
    )
    if coordinates_are_inverted:
        latitude, longitude = longitude, latitude
    return {
        'id': station.id,
        'codigo': station.codigo_estacion,
        'nombre': station.nombre,
        'tipo': station.tipo,
        'latitud': latitude,
        'longitud': longitude,
        'elevacion': station.elevacion_msnm,
        'cuenca_id': station.cuenca_id,
        'photos': station_photos(station.codigo_estacion),
    }


def station_photos(station_code):
    station_directory = IMAGES_PATH / station_code
    if not station_directory.is_dir():
        return []
    return [
        f'/static/img/{quote(station_code)}/{quote(image.name)}'
        for image in sorted(station_directory.iterdir(), key=lambda item: item.name.lower())
        if image.is_file() and image.suffix.lower() in IMAGE_EXTENSIONS
    ]


def basin_to_dict(basin):
    if basin is None:
        return {}
    return {
        'id': basin.id,
        'codigo_cuenca': basin.codigo_cuenca,
        'nombre': basin.nombre,
        'area_km2': basin.area_km2,
        'perimetro_km': basin.perimetro_km,
        'densidad_drenaje': basin.densidad_drenaje,
        'elevacion_minima': basin.elevacion_minima,
        'elevacion_maxima': basin.elevacion_maxima,
        'elevacion_media': basin.elevacion_media,
        'pendiente_media': basin.pendiente_media,
        'longitud_rio_km': basin.longitud_rio_km,
        'longitud_cuenca_km': basin.longitud_cuenca_km,
        'factor_forma': basin.factor_forma,
        'coeficiente_gravelius': basin.coeficiente_gravelius,
        'relacion_elongacion': basin.relacion_elongacion,
        'relacion_circularidad': basin.relacion_circularidad,
        'relieve_total_m': basin.relieve_total_m,
        'pendiente_minima': basin.pendiente_minima,
        'pendiente_maxima': basin.pendiente_maxima,
        'integral_hipsometrica': basin.integral_hipsometrica,
    }


def admin_required(view):
    def wrapped(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin_login', next=request.path))
        return view(*args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


def form_float(name):
    value = request.form.get(name, '').strip()
    return float(value) if value else None


def nullable_float(value):
    value = value.strip()
    if not value or value in {'---', '--', '---.-'}:
        return None
    return float(value)


def parse_weather_file(file_storage):
    rows = []
    for line_number, raw_line in enumerate(file_storage.stream, start=1):
        line = raw_line.decode('utf-8-sig', errors='replace').strip()
        if not line or line.startswith('Date') or line.startswith('Temp'):
            continue
        fields = line.split()
        if len(fields) < 19:
            continue
        try:
            date_value = datetime.strptime(
                f'{fields[0]} {fields[1]}', '%d/%m/%y %H:%M'
            )
            rows.append(MeteorologicalData(
                fecha_hora=date_value,
                precipitacion=nullable_float(fields[17]),
                temperatura=nullable_float(fields[2]),
                humedad_relativa=nullable_float(fields[5]),
            ))
        except (ValueError, IndexError) as error:
            raise ValueError(f'Fila {line_number}: formato no válido') from error
    if not rows:
        raise ValueError('El archivo no contiene filas meteorológicas válidas.')
    return rows


def parse_hydrology_file(file_storage):
    rows = []
    skipped_empty = 0
    file_storage.stream.seek(0)
    text_stream = (
        raw_line.decode('utf-8-sig', errors='replace')
        for raw_line in file_storage.stream
    )
    reader = csv.reader(text_stream, delimiter=',', skipinitialspace=True)
    for line_number, fields in enumerate(reader, start=1):
        fields = [field.strip() for field in fields]
        if not fields or not any(fields) or fields[0].startswith('#'):
            continue
        if len(fields) < 3 or fields[0].lower() in {'fecha', 'date'}:
            continue
        if not fields[0] or not fields[1] or not fields[2]:
            skipped_empty += 1
            continue
        try:
            date_value = datetime.strptime(
                f'{fields[0]} {fields[1]}', '%Y-%m-%d %H:%M'
            )
            rows.append(HydrologicalData(
                fecha_hora=date_value,
                caudal_m3_s=float(fields[2]),
            ))
        except (ValueError, IndexError) as error:
            raise ValueError(
                f'Fila {line_number}: use fecha YYYY-MM-DD, hora H:MM y caudal numérico'
            ) from error
    if not rows:
        raise ValueError('El archivo no contiene filas hidrológicas válidas.')
    return rows

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if ADMIN_PASSWORD_HASH and username == ADMIN_USER and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_authenticated'] = True
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        error = 'Configura ADMIN_PASSWORD en el entorno.' if not ADMIN_PASSWORD_HASH else 'Usuario o contraseña incorrectos.'
    return render_template('admin_login.html', error=error)


@app.get('/admin/logout')
def admin_logout():
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin_login'))


@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    message = None
    error = None
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            with Session(engine) as db:
                if action == 'basin':
                    db.add(Basin(
                        codigo_cuenca=request.form['codigo_cuenca'].strip(),
                        nombre=request.form['nombre'].strip(),
                        area_km2=form_float('area_km2'),
                        perimetro_km=form_float('perimetro_km'),
                        densidad_drenaje=form_float('densidad_drenaje'),
                        elevacion_minima=form_float('elevacion_minima'),
                        elevacion_maxima=form_float('elevacion_maxima'),
                        elevacion_media=form_float('elevacion_media'),
                        pendiente_media=form_float('pendiente_media'),
                        longitud_rio_km=form_float('longitud_rio_km'),
                    ))
                    message = 'Cuenca guardada correctamente.'
                elif action == 'station':
                    db.add(Station(
                        codigo_estacion=request.form['codigo_estacion'].strip(),
                        cuenca_id=int(request.form['cuenca_id']),
                        nombre=request.form['nombre'].strip(),
                        fecha_instalacion=datetime.strptime(request.form['fecha_instalacion'], '%Y-%m-%d').date() if request.form.get('fecha_instalacion') else None,
                        longitud=float(request.form['longitud']),
                        latitud=float(request.form['latitud']),
                        elevacion_msnm=form_float('elevacion_msnm'),
                        tipo=request.form['tipo'],
                    ))
                    message = 'Estación guardada correctamente.'
                elif action in {'weather', 'hydrology'}:
                    station_id = int(request.form['station_id'])
                    station = db.get(Station, station_id)
                    upload = request.files.get('data_file')
                    if station is None or upload is None or not upload.filename:
                        raise ValueError('Seleccione una estación y un archivo.')
                    expected_type = 'Meteorologica' if action == 'weather' else 'Hidrologica'
                    if station.tipo != expected_type:
                        raise ValueError(f'La estación seleccionada debe ser {expected_type}.')
                    records = parse_weather_file(upload) if action == 'weather' else parse_hydrology_file(upload)
                    for record in records:
                        record.estacion_id = station_id
                    db.add_all(records)
                    message = f'{len(records)} registros cargados correctamente.'
                else:
                    raise ValueError('Operación no reconocida.')
                db.commit()
        except (KeyError, ValueError, TypeError) as exc:
            error = str(exc)
        except Exception as exc:
            error = f'No se pudo guardar la información: {exc}'

    with Session(engine) as db:
        basins_rows = db.scalars(select(Basin).order_by(Basin.nombre)).all()
        stations_rows = db.scalars(select(Station).order_by(Station.nombre)).all()
    return render_template('admin.html', basins=basins_rows, stations=stations_rows, message=message, error=error)


@app.get('/api/basins')
def basins():
    geojson = load_geojson()

    with Session(engine) as session:
        basin_rows = session.scalars(select(Basin)).all()
        basins_by_code = {basin.codigo_cuenca: basin for basin in basin_rows}
        default_basin = basin_rows[0] if len(basin_rows) == 1 else None
        features = []
        for feature in geojson.get('features', []):
            properties = feature.get('properties') or {}
            code = properties.get('codigo_cuenca') or properties.get('CODIGO')
            basin = basins_by_code.get(code) or default_basin
            features.append({
                'type': feature.get('type', 'Feature'),
                'geometry': feature.get('geometry'),
                'properties': {
                    **properties,
                    'database': basin_to_dict(basin),
                },
            })

    return jsonify({'type': 'FeatureCollection', 'features': features})


@app.get('/api/hypsometric')
def hypsometric():
    payload = calculate_hypsometric()
    if 'error' in payload:
        response = {key: value for key, value in payload.items() if key != '_status'}
        return jsonify(response), payload.get('_status', 500)
    return jsonify(payload)


@lru_cache(maxsize=1)
def calculate_hypsometric():
    geojson = load_geojson()

    features = geojson.get('features', [])
    if not features:
        return {'error': 'No hay geometría de cuenca disponible', '_status': 404}

    geometry = features[0].get('geometry')
    try:
        import numpy as np
        import rasterio
        from rasterio.mask import mask
        from rasterio.warp import transform_geom

        with rasterio.open(RASTER_PATH) as raster:
            raster_geometry = transform_geom(
                'EPSG:4326', raster.crs, geometry, precision=2
            )
            clipped, _ = mask(raster, [raster_geometry], crop=True, filled=False)
            elevations = clipped[0].compressed()
    except ImportError as error:
        return {'error': f'Falta una dependencia geoespacial en el entorno: {error}', '_status': 503}
    except (OSError, ValueError) as error:
        return {'error': f'No se pudo leer el raster: {error}', '_status': 500}

    elevations = elevations[elevations > 0]
    if elevations.size == 0:
        return {'error': 'El raster no contiene elevaciones dentro de la cuenca', '_status': 422}

    minimum = float(elevations.min())
    maximum = float(elevations.max())
    mean = float(elevations.mean())
    bins = 25
    levels = [minimum + (maximum - minimum) * index / (bins - 1) for index in range(bins)]
    curve = [
        {
            'elevacion': round(level, 1),
            'elevacion_relativa': round((level - minimum) / (maximum - minimum), 4) if maximum > minimum else 0,
            'area_relativa': round(float((elevations >= level).sum() / elevations.size), 4),
        }
        for level in levels
    ]
    return {
        'minima': round(minimum, 1),
        'maxima': round(maximum, 1),
        'media': round(mean, 1),
        'pixeles': int(elevations.size),
        'curve': curve,
    }


@app.get('/api/stations')
def stations():
    station_type = request.args.get('tipo')
    with Session(engine) as session:
        query = select(Station).order_by(Station.nombre)
        if station_type:
            query = query.where(Station.tipo == station_type)
        results = session.scalars(query).all()
        return jsonify([station_to_dict(station) for station in results])


@app.get('/api/data')
def historical_data():
    try:
        station_id = int(request.args['station_id'])
        start_date = parse_date(request.args.get('start_date'), 'start_date')
        end_date = parse_date(request.args.get('end_date'), 'end_date')
    except (KeyError, TypeError, ValueError) as error:
        return jsonify({'error': str(error) or 'station_id es obligatorio'}), 400

    if start_date and end_date and start_date > end_date:
        return jsonify({'error': 'La fecha inicial no puede ser posterior a la fecha final'}), 400

    variable = request.args.get('variable', 'precipitation')
    granularity = request.args.get('granularity', 'day')
    if granularity not in {'day', 'month', 'year'}:
        return jsonify({'error': 'La agrupación debe ser day, month o year'}), 400

    with Session(engine) as session:
        station = session.scalar(
            select(Station).options(joinedload(Station.cuenca)).where(Station.id == station_id)
        )
        if station is None:
            return jsonify({'error': 'Estación no encontrada'}), 404

        if station.tipo == 'Hidrologica':
            if variable != 'flow':
                variable = 'flow'
            value_column = HydrologicalData.caudal_m3_s
            timestamp_column = HydrologicalData.fecha_hora
            data_query = select(timestamp_column, value_column).where(
                HydrologicalData.estacion_id == station_id
            )
        else:
            allowed_variables = {
                'precipitation': MeteorologicalData.precipitacion,
                'temperature': MeteorologicalData.temperatura,
                'humidity': MeteorologicalData.humedad_relativa,
            }
            value_column = allowed_variables.get(variable, MeteorologicalData.precipitacion)
            variable = variable if variable in allowed_variables else 'precipitation'
            timestamp_column = MeteorologicalData.fecha_hora
            data_query = select(timestamp_column, value_column).where(
                MeteorologicalData.estacion_id == station_id
            )

        if start_date:
            data_query = data_query.where(
                timestamp_column >= datetime.combine(start_date, datetime.min.time())
            )
        # El límite final es exclusivo para incluir todas las horas del último día.
        if end_date:
            from datetime import timedelta
            data_query = data_query.where(
                timestamp_column < datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            )

        rows = session.execute(data_query.order_by(timestamp_column)).all()
        available_query = select(func.min(timestamp_column), func.max(timestamp_column)).where(
            timestamp_column.is_not(None)
        )
        if station.tipo == 'Hidrologica':
            available_query = available_query.where(HydrologicalData.estacion_id == station_id)
        else:
            available_query = available_query.where(MeteorologicalData.estacion_id == station_id)
        available_start, available_end = session.execute(available_query).one()

        if variable == 'precipitation':
            series = precipitation_series(rows, granularity)
        else:
            grouped = defaultdict(list)
            for timestamp, value in rows:
                if timestamp is None or value is None:
                    continue
                if granularity == 'year':
                    period = timestamp.strftime('%Y')
                elif granularity == 'month':
                    period = timestamp.strftime('%Y-%m')
                else:
                    period = timestamp.strftime('%Y-%m-%d')
                grouped[period].append(float(value))

            series = []
            for period, values in sorted(grouped.items()):
                average = sum(values) / len(values)
                series.append({
                    'fecha': period,
                    'minimo': rounded_value(min(values)),
                    'maximo': rounded_value(max(values)),
                    'media': rounded_value(average),
                    'valor': rounded_value(average),
                })

        basin = station.cuenca
        return jsonify({
            'station': station_to_dict(station),
            'variable': variable,
            'granularity': granularity,
            'value_label': 'Total acumulado' if variable == 'precipitation' else 'Media',
            'minimum_label': 'Mínimo diario' if variable == 'precipitation' and granularity != 'day' else 'Mínimo',
            'maximum_label': 'Máximo diario' if variable == 'precipitation' and granularity != 'day' else 'Máximo',
            'available_start': series_date(available_start) if available_start else None,
            'available_end': series_date(available_end) if available_end else None,
            'unit': 'm3/s' if station.tipo == 'Hidrologica' else (
                'mm' if variable == 'precipitation' else '°C' if variable == 'temperature' else '%'
            ),
            'basin': {
                'nombre': basin.nombre,
                'area_km2': basin.area_km2,
                'perimetro_km': basin.perimetro_km,
                'densidad_drenaje': basin.densidad_drenaje,
                'elevacion_minima': basin.elevacion_minima,
                'elevacion_maxima': basin.elevacion_maxima,
                'elevacion_media': basin.elevacion_media,
                'pendiente_media': basin.pendiente_media,
                'longitud_rio_km': basin.longitud_rio_km,
            },
            'series': series,
        })

if __name__ == '__main__':
    app.run(debug=True)