document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('sidebar');
    const openButton = document.getElementById('open-sidebar');
    const closeButton = document.getElementById('close-sidebar');
    const themeSelect = document.getElementById('theme-select');
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
    const stationSelect = document.getElementById('station-select');
    const variableSelect = document.getElementById('variable');
    const granularitySelect = document.getElementById('granularity');
    const startDate = document.getElementById('start-date');
    const endDate = document.getElementById('end-date');
    const chartCanvas = document.getElementById('data-chart');
    const hypsometricCanvas = document.getElementById('hypsometric-chart');
    let stations = [];
    let chart;
    let hypsometricChart;
    let map;
    let basinLayer;
    let dataController;
    let currentPhotos = [];
    let currentPhotoIndex = 0;

    const applyTheme = (preference) => {
        const theme = preference === 'system'
            ? (systemTheme.matches ? 'dark' : 'light')
            : preference;

        document.documentElement.dataset.theme = theme;
        document.body.dataset.theme = theme;
    };

    const savedTheme = localStorage.getItem('ichu-theme') || 'system';
    themeSelect.value = savedTheme;
    applyTheme(savedTheme);

    themeSelect.addEventListener('change', () => {
        const preference = themeSelect.value;
        localStorage.setItem('ichu-theme', preference);
        applyTheme(preference);
        if (basinLayer) basinLayer.setStyle(basinStyle());
    });

    systemTheme.addEventListener('change', () => {
        if (themeSelect.value === 'system') {
            applyTheme('system');
            if (basinLayer) basinLayer.setStyle(basinStyle());
        }
    });

    const setSidebarState = (isOpen) => {
        sidebar.classList.toggle('is-open', isOpen);
        sidebar.setAttribute('aria-hidden', String(!isOpen));
        openButton.setAttribute('aria-expanded', String(isOpen));

        if (isOpen) {
            closeButton.focus();
        } else {
            openButton.focus();
        }

        window.setTimeout(() => {
            if (window.mapInstance) {
                window.mapInstance.invalidateSize();
            }
        }, 240);
    };

    const showContext = (context) => {
        document.querySelectorAll('.context-view').forEach((view) => {
            view.classList.toggle('is-active', view.classList.contains(`${context}-view`));
        });
    };

    openButton.addEventListener('click', () => setSidebarState(true));
    closeButton.addEventListener('click', () => setSidebarState(false));

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && sidebar.classList.contains('is-open')) {
            setSidebarState(false);
        }
    });

    if (typeof L !== 'undefined') {
        map = L.map('map', { zoomControl: true }).setView([-12.78, -74.97], 11);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        window.mapInstance = map;
    }

    const setStationDetails = (station) => {
        document.getElementById('station-name').textContent = station.nombre;
        document.getElementById('station-type').textContent = `Tipo: ${station.tipo}`;
        document.getElementById('station-altitude').textContent = station.elevacion
            ? `Elevación: ${station.elevacion} msnm`
            : '';
        variableSelect.innerHTML = station.tipo === 'Hidrologica'
            ? '<option value="flow">Caudal</option>'
            : '<option value="precipitation">Precipitación</option><option value="temperature">Temperatura</option><option value="humidity">Humedad relativa</option>';
        renderPhotoCarousel(station.photos || []);
    };

    const renderPhotoCarousel = (photos) => {
        const carousel = document.getElementById('photo-carousel');
        const controls = document.getElementById('carousel-controls');
        const dots = document.getElementById('carousel-dots');
        const counter = document.getElementById('photo-counter');
        currentPhotos = photos;
        currentPhotoIndex = 0;
        carousel.innerHTML = '';
        dots.innerHTML = '';

        if (!photos.length) {
            carousel.innerHTML = '<p class="photo-empty">No hay fotografías para esta estación.</p>';
            controls.hidden = true;
            counter.textContent = 'Sin fotografías';
            return;
        }

        photos.forEach((photo, index) => {
            const image = document.createElement('img');
            image.src = photo;
            image.alt = `Fotografía ${index + 1} de la estación seleccionada`;
            image.className = 'carousel-image';
            image.hidden = index !== 0;
            carousel.appendChild(image);

            const dot = document.createElement('button');
            dot.type = 'button';
            dot.className = `carousel-dot${index === 0 ? ' is-active' : ''}`;
            dot.setAttribute('aria-label', `Mostrar fotografía ${index + 1}`);
            dot.addEventListener('click', () => showPhoto(index));
            dots.appendChild(dot);
        });
        controls.hidden = false;
        counter.textContent = `${photos.length} fotografía${photos.length === 1 ? '' : 's'}`;
    };

    const showPhoto = (index) => {
        if (!currentPhotos.length) return;
        currentPhotoIndex = (index + currentPhotos.length) % currentPhotos.length;
        document.querySelectorAll('.carousel-image').forEach((image, imageIndex) => {
            image.hidden = imageIndex !== currentPhotoIndex;
        });
        document.querySelectorAll('.carousel-dot').forEach((dot, dotIndex) => {
            dot.classList.toggle('is-active', dotIndex === currentPhotoIndex);
        });
    };

    const renderBasin = (basin, geometryProperties = {}) => {
        const values = {
            ...geometryProperties,
            ...basin,
            area_km2: basin.area_km2 ?? geometryProperties.AREA,
            perimetro_km: basin.perimetro_km ?? geometryProperties.PERIMETRO
        };
        const groups = [
            {
                title: 'Forma y tamaño',
                metrics: [
                    ['codigo_cuenca', 'Código', ''],
                    ['nombre', 'Nombre', ''],
                    ['area_km2', 'Área de la cuenca', 'km²'],
                    ['perimetro_km', 'Perímetro', 'km'],
                    ['longitud_cuenca_km', 'Longitud geométrica', 'km'],
                    ['longitud_rio_km', 'Longitud de río', 'km']
                ]
            },
            {
                title: 'Índices de forma',
                metrics: [
                    ['factor_forma', 'Factor de forma', ''],
                    ['coeficiente_gravelius', 'Coeficiente de Gravelius', ''],
                    ['relacion_elongacion', 'Relación de elongación', ''],
                    ['relacion_circularidad', 'Relación de circularidad', '']
                ]
            },
            {
                title: 'Relieve y pendiente',
                metrics: [
                    ['elevacion_minima', 'Altitud mínima', 'msnm'],
                    ['elevacion_media', 'Altitud media', 'msnm'],
                    ['elevacion_maxima', 'Altitud máxima', 'msnm'],
                    ['relieve_total_m', 'Relieve total', 'm'],
                    ['pendiente_minima', 'Pendiente mínima', '°'],
                    ['pendiente_media', 'Pendiente media', '°'],
                    ['pendiente_maxima', 'Pendiente máxima', '°'],
                    ['integral_hipsometrica', 'Integral hipsométrica', '']
                ]
            },
            {
                title: 'Red de drenaje',
                metrics: [
                    ['densidad_drenaje', 'Densidad de drenaje', 'km/km²'],
                    ['frecuencia_drenaje', 'Frecuencia de ríos', '1/km²'],
                    ['orden_strahler', 'Orden de Strahler', '']
                ]
            }
        ];
        document.getElementById('basin-parameters').innerHTML = groups.map((group) => `
            <section class="metric-group">
                <h3>${group.title}</h3>
                <div class="metric-list">
                    ${group.metrics.map(([key, label, unit]) => `
                        <div class="metric-row">
                            <span>${label}</span>
                            <strong>${values[key] ?? '-'} ${unit}</strong>
                        </div>
                    `).join('')}
                </div>
            </section>
        `).join('');
    };

    const loadHypsometric = async () => {
        const response = await fetch('/api/hypsometric');
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'No se pudo calcular la curva hipsométrica');

        document.getElementById('basin-minimum').textContent = `${payload.minima} msnm`;
        document.getElementById('basin-mean').textContent = `${payload.media} msnm`;
        document.getElementById('basin-maximum').textContent = `${payload.maxima} msnm`;
        if (hypsometricChart) hypsometricChart.destroy();
        hypsometricChart = new Chart(hypsometricCanvas, {
            type: 'line',
            data: {
                labels: payload.curve.map((point) => point.elevacion),
                datasets: [{
                    label: 'Área relativa',
                    data: payload.curve.map((point) => point.area_relativa),
                    borderColor: '#286b4b',
                    backgroundColor: 'rgba(40, 107, 75, 0.16)',
                    pointRadius: 2,
                    fill: true,
                    tension: 0.25
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: 'Elevación (msnm)' }, ticks: { maxTicksLimit: 8 } },
                    y: { min: 0, max: 1, title: { display: true, text: 'Área relativa' } }
                }
            }
        });
    };

        const basinStyle = () => ({
            color: document.documentElement.dataset.theme === 'dark' ? '#a8d5a2' : '#286b4b',
            weight: 2,
            opacity: 0.9,
            fillColor: document.documentElement.dataset.theme === 'dark' ? '#4e8f62' : '#73a96d',
            fillOpacity: 0.27
        });

        const loadBasins = async () => {
            if (!map) return;
            const response = await fetch('/api/basins');
            const geojson = await response.json();
            basinLayer = L.geoJSON(geojson, {
                style: basinStyle,
                onEachFeature: (feature, layer) => {
                    const properties = feature.properties || {};
                    const basin = properties.database || {};
                    layer.bindTooltip(basin.nombre || 'Cuenca del río Ichu', { sticky: true });
                    layer.on({
                        mouseover: (event) => event.target.setStyle({ weight: 3, fillOpacity: 0.4 }),
                        mouseout: (event) => basinLayer.resetStyle(event.target),
                        click: () => {
                            renderBasin(basin, properties);
                            showContext('basin');
                            setSidebarState(true);
                            loadHypsometric().catch((error) => console.error(error));
                        }
                    });
                }
            }).addTo(map);
            if (basinLayer.getBounds().isValid()) {
                map.fitBounds(basinLayer.getBounds(), { padding: [40, 40] });
            }
        };

    const updateChart = async () => {
        const stationId = stationSelect.value;
        if (!stationId) return;

        if (dataController) dataController.abort();
        dataController = new AbortController();

        const params = new URLSearchParams({
            station_id: stationId,
            variable: variableSelect.value,
            granularity: granularitySelect.value
        });
        if (startDate.value) params.set('start_date', startDate.value);
        if (endDate.value) params.set('end_date', endDate.value);

        const response = await fetch(`/api/data?${params}`, {
            signal: dataController.signal
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'No se pudieron obtener los datos');
        }

        if (!startDate.value && payload.available_start) startDate.value = payload.available_start;
        if (!endDate.value && payload.available_end) endDate.value = payload.available_end;

        const labels = payload.series.map((item) => item.fecha);
        const datasets = [
            { label: payload.maximum_label, data: payload.series.map((item) => item.maximo), borderColor: '#d9693e', backgroundColor: 'rgba(217, 105, 62, 0.16)', fill: true },
            { label: payload.value_label, data: payload.series.map((item) => item.valor), borderColor: '#2d7764', backgroundColor: 'rgba(45, 119, 100, 0.12)', fill: true },
            { label: payload.minimum_label, data: payload.series.map((item) => item.minimo), borderColor: '#5573a4', backgroundColor: 'rgba(85, 115, 164, 0.12)', fill: true }
        ];

        document.getElementById('minimum').textContent = payload.series.length ? payload.series.at(-1).minimo : '-';
        document.getElementById('maximum').textContent = payload.series.length ? payload.series.at(-1).maximo : '-';
        document.getElementById('mean').textContent = payload.series.length ? payload.series.at(-1).valor : '-';
        document.getElementById('mean-label').textContent = payload.value_label;
        document.getElementById('chart-unit').textContent = payload.unit ? `(${payload.unit})` : '';
        renderBasin(payload.basin);

        if (chart) chart.destroy();
        chart = new Chart(chartCanvas, {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    x: {
                        ticks: { autoSkip: true, maxTicksLimit: 12, maxRotation: 0 }
                    },
                    y: { beginAtZero: false }
                }
            }
        });
    };

    const loadStations = async () => {
        const response = await fetch('/api/stations');
        stations = await response.json();
        stationSelect.innerHTML = stations.length
            ? stations.map((station) => `<option value="${station.id}">${station.nombre} (${station.tipo})</option>`).join('')
            : '<option value="">No hay estaciones registradas</option>';

        stations.forEach((station) => {
            if (!map) return;
            const stationIcon = L.divIcon({
                className: `station-marker ${station.tipo === 'Hidrologica' ? 'hydrological-marker' : 'meteorological-marker'}`,
                html: `<span aria-hidden="true"></span>`,
                iconSize: [22, 22],
                iconAnchor: [11, 11],
                popupAnchor: [0, -13]
            });
            const marker = L.marker([station.latitud, station.longitud], { icon: stationIcon }).addTo(map);
            marker.bindTooltip(
                `<strong>${station.nombre}</strong><br>Tipo: ${station.tipo}<br>Longitud: ${station.longitud.toFixed(6)}<br>Latitud: ${station.latitud.toFixed(6)}`,
                {
                    className: `station-tooltip ${station.tipo === 'Hidrologica' ? 'hydrological-tooltip' : 'meteorological-tooltip'}`,
                    direction: 'top',
                    offset: [0, -10]
                }
            );
            marker.bindPopup(`<strong>${station.nombre}</strong><br><span>${station.codigo}</span><br>${station.tipo}`);
            marker.on('click', () => {
                stationSelect.value = String(station.id);
                setStationDetails(station);
                showContext('station');
                setSidebarState(true);
                updateChart().catch((error) => console.error(error));
            });
        });

        if (stations[0]) {
            stationSelect.value = String(stations[0].id);
            setStationDetails(stations[0]);
            updateChart().catch((error) => console.error(error));
        }
    };

    stationSelect.addEventListener('change', () => {
        const station = stations.find((item) => String(item.id) === stationSelect.value);
        if (station) {
            setStationDetails(station);
            showContext('station');
            startDate.value = '';
            endDate.value = '';
            updateChart().catch((error) => console.error(error));
        }
    });
    variableSelect.addEventListener('change', () => {
        updateChart().catch((error) => console.error(error));
    });
    granularitySelect.addEventListener('change', () => {
        updateChart().catch((error) => console.error(error));
    });
    document.getElementById('update-chart').addEventListener('click', () => {
        updateChart().catch((error) => {
            if (error.name !== 'AbortError') console.error(error);
        });
    });
    document.getElementById('previous-photo').addEventListener('click', () => showPhoto(currentPhotoIndex - 1));
    document.getElementById('next-photo').addEventListener('click', () => showPhoto(currentPhotoIndex + 1));
    loadStations().catch((error) => console.error(error));
    loadBasins().catch((error) => console.error(error));
});
