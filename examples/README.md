# QUCORE Example Data

This directory contains minimal example datasets for testing QUCORE.

## QUCORE_MinExample_Cuxhaven_Germany.gpkg

A minimal GeoPackage example route near **Cuxhaven, Germany** for quick testing and demonstration of QUCORE's corridor planning capabilities.

### How to use

1. Open QGIS and activate the QUCORE plugin
2. Go to **Plugins → QUCORE** or use the toolbar button
3. Import the example file via **File → Import GeoPackage** (or drag & drop into QGIS)
4. The route with pre-configured waypoints will be loaded, and FG/CV/GRB buffers will be calculated automatically

### Contents

- Pre-defined waypoint route with altitude and speed parameters
- Suitable for testing all QUCORE features: buffer calculation, asymmetric wind drift, VLOS calculator, and report generation
