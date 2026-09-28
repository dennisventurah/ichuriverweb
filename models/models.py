from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Basin(Base):
    __tablename__ = 'cuencas'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_cuenca: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150))
    area_km2: Mapped[Optional[float]] = mapped_column(Float)
    perimetro_km: Mapped[Optional[float]] = mapped_column(Float)
    densidad_drenaje: Mapped[Optional[float]] = mapped_column(Float)
    elevacion_minima: Mapped[Optional[float]] = mapped_column(Float)
    elevacion_maxima: Mapped[Optional[float]] = mapped_column(Float)
    elevacion_media: Mapped[Optional[float]] = mapped_column(Float)
    pendiente_media: Mapped[Optional[float]] = mapped_column(Float)
    longitud_rio_km: Mapped[Optional[float]] = mapped_column(Float)
    longitud_cuenca_km: Mapped[Optional[float]] = mapped_column(Float)
    factor_forma: Mapped[Optional[float]] = mapped_column(Float)
    coeficiente_gravelius: Mapped[Optional[float]] = mapped_column(Float)
    relacion_elongacion: Mapped[Optional[float]] = mapped_column(Float)
    relacion_circularidad: Mapped[Optional[float]] = mapped_column(Float)
    relieve_total_m: Mapped[Optional[float]] = mapped_column(Float)
    pendiente_minima: Mapped[Optional[float]] = mapped_column(Float)
    pendiente_maxima: Mapped[Optional[float]] = mapped_column(Float)
    integral_hipsometrica: Mapped[Optional[float]] = mapped_column(Float)

    estaciones: Mapped[list['Station']] = relationship(back_populates='cuenca')


class Station(Base):
    __tablename__ = 'estaciones'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_estacion: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    cuenca_id: Mapped[int] = mapped_column(ForeignKey('cuencas.id'), index=True)
    nombre: Mapped[str] = mapped_column(String(150))
    fecha_instalacion: Mapped[Optional[date]] = mapped_column(Date)
    longitud: Mapped[float] = mapped_column(Float)
    latitud: Mapped[float] = mapped_column(Float)
    elevacion_msnm: Mapped[Optional[float]] = mapped_column(Float)
    tipo: Mapped[str] = mapped_column(String(20), index=True)

    cuenca: Mapped[Basin] = relationship(back_populates='estaciones')
    datos_hidrologicos: Mapped[list['HydrologicalData']] = relationship(
        back_populates='estacion', cascade='all, delete-orphan'
    )
    datos_meteorologicos: Mapped[list['MeteorologicalData']] = relationship(
        back_populates='estacion', cascade='all, delete-orphan'
    )


class HydrologicalData(Base):
    __tablename__ = 'datos_hidrologico'
    __table_args__ = (
        Index('ix_datos_hidrologico_estacion_fecha', 'estacion_id', 'fecha_hora'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estacion_id: Mapped[int] = mapped_column(ForeignKey('estaciones.id'), index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, index=True)
    caudal_m3_s: Mapped[float] = mapped_column(Float)

    estacion: Mapped[Station] = relationship(back_populates='datos_hidrologicos')


class MeteorologicalData(Base):
    __tablename__ = 'datos_meteorologico'
    __table_args__ = (
        Index('ix_datos_meteorologico_estacion_fecha', 'estacion_id', 'fecha_hora'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estacion_id: Mapped[int] = mapped_column(ForeignKey('estaciones.id'), index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, index=True)
    precipitacion: Mapped[Optional[float]] = mapped_column(Float)
    temperatura: Mapped[Optional[float]] = mapped_column(Float)
    humedad_relativa: Mapped[Optional[float]] = mapped_column(Float)

    estacion: Mapped[Station] = relationship(back_populates='datos_meteorologicos')
