# Tesis_Multimodelo
Proyecto final de la materia **Preprocesamiento para Ciencia de Datos**.

## Tema

Integración, perfilado y limpieza de datos bibliográficos de la UNAM en **Ciencias e  Ingenieria de la Computación**, correspondientes al periodo **marzo de 2024 a diciembre de 2025**.

## Objetivo

Construir una base bibliográfica limpia, integrada, de-duplicada y curada, usando un modelo canónico común para publicaciones académicas de la UNAM en Ciencias de la Computación.

El resultado final es una base en formato artículo–autor, donde cada fila representa una relación entre un artículo y un autor UNAM.

## Fuentes bibliográficas

Se trabajaron ocho fuentes:

* ACM Digital Library
* EBSCO
* Engineering Village
* IEEE Xplore
* ProQuest
* ScienceDirect
* Scopus
* Web of Science

## Modelo canónico

La base final conserva las siguientes 14 columnas:

```text
indice
Titulo
Año
Autor_norm
Afiliacion1
Afiliacion2
ISBN
ISSN
Doi
URL
Area
Subarea
Keywords
Abstract
```

## Áreas válidas

```text
ISBD  Ingeniería de Software y Bases de Datos
CC    Computación Científica
IA    Inteligencia Artificial
TC    Teoría de la Computación
SIAV  Señales, Imágenes y Ambientes Virtuales
RS    Redes y Seguridad
```


## Estructura del repositorio

```text
00_control/
01_recoleccion_manual/
02_modelo canonico/
notebooks/
```

## Flujo general del proyecto

```text
recolección manual
→ modelo canónico
→ integración preliminar
→ perfilado
→ limpieza
→ normalización de autores y afiliaciones
→ de-duplicación y fusión
→ curaduría manual
→ base limpia final
```

## Autor

Luis David Aguilar Colorado

Lic. en Física | Estudiante de Maestría (PCIC, UNAM)