# QUCORE – QGIS UAS Corridor Outlining & Routing Engine

🇩🇪 **Deutsch** | 🇬🇧 [**English Version**](#english-version)

**QUCORE** ist ein professionelles, SORA-konformes QGIS-Plugin zur interaktiven Planung von UAS-Flugkorridoren. Es berechnet dynamisch und in Echtzeit die **Flight Geography (FG)**, das **Contingency Volume (CV)** und den **Ground Risk Buffer (GRB)** basierend auf offiziellen Leitlinien der EASA und des LBA.

![QUCORE Icon](icon.png)

## Installation

1. Lade dieses Repository als ZIP-Datei herunter (über GitHub: *Code* -> *Download ZIP*).
2. Öffne QGIS.
3. Gehe zu **Erweiterungen** -> **Erweiterungen verwalten und installieren...** -> **Aus ZIP installieren**.
4. Wähle die heruntergeladene ZIP-Datei aus und klicke auf **Erweiterung installieren**.

---

## Hauptfeatures

* **Interaktive Routenplanung:** Setze Wegpunkte direkt auf der Karte per Klick.
* **Echtzeit-Berechnung:** Buffers (FG/CV/GRB) passen sich beim Verschieben von Wegpunkten per Drag-and-Drop sofort an.
* **Wegpunktspezifische Parameter:** Höhe, Geschwindigkeit und Korridorbreite können für jeden Wegpunkt individuell festgelegt werden.
* **SORA-Demografie-Analyse:** Automatische Ermittlung der durchschnittlichen Bevölkerungsdichte im Adjacent Area (AA) sowie Angabe der maximalen Bevölkerungsdichte im Ground Risk Buffer (GRB) zur präzisen Risikobewertung.
* **VLOS-Rechner & Visualisierung:** Automatische Berechnung und Anzeige der ALOS/DLOS-Reichweite um die Pilotenposition.
* **Multilingual:** Volle Unterstützung für Deutsch (DE) und Englisch (EN).
* **Umfangreiche Exporte:** Unterstützt KML, .dipul (DIPUL-Standard), SkyDemon (.flightplan), GeoJSON, GeoPackage und automatisierte SORA-Word-Dokumente (.docx) inklusive Kartenausschnitt.

---

## Lizenz & Nutzungsbedingungen

### 1. Private & Nicht-kommerzielle Nutzung
Die Nutzung dieses Plugins für **private und nicht-kommerzielle Zwecke** sowie zu Ausbildungszwecken ist vollständig **kostenfrei**. Du darfst den Code für deinen privaten Gebrauch anpassen.

### 2. Kommerzielle Nutzung (Unternehmen / Behörden)
* **Testphase:** Gewerbliche Nutzer dürfen das Plugin für einen Zeitraum von **1 Monat** kostenfrei testen und evaluieren.
* **Nach der Testphase:** Für eine dauerhafte kommerzielle Nutzung kontaktieren Sie bitte den Autor unter **tim.strohbach [at] gmx.de** für eine entsprechende Lizenzierung. 

### 3. Gewährleistungsausschluss
Die Software wird ohne Mängelgewähr ("As-Is") zur Verfügung gestellt. Der Autor übernimmt keinerlei Haftung für die Richtigkeit der Berechnungen oder eventuelle Schäden im Betrieb.

---

*Entwickelt mit ❤️ für die UAS-Community.*

---

<a id="english-version"></a>
# QUCORE – QGIS UAS Corridor Outlining & Routing Engine (English)

**QUCORE** is a professional, SORA-compliant QGIS plugin for interactive planning of UAS flight corridors. It calculates the **Flight Geography (FG)**, the **Contingency Volume (CV)**, and the **Ground Risk Buffer (GRB)** dynamically and in real time based on official EASA and LBA guidelines.

## Installation

1. Download this repository as a ZIP file (via GitHub: *Code* -> *Download ZIP*).
2. Open QGIS.
3. Go to **Plugins** -> **Manage and Install Plugins...** -> **Install from ZIP**.
4. Select the downloaded ZIP file and click **Install Plugin**.

---

## Key Features

* **Interactive Route Planning:** Add waypoints directly on the map with a simple click.
* **Real-time Calculation:** Safety buffers (FG/CV/GRB) adapt instantly when moving waypoints via drag-and-drop.
* **Waypoint-specific Parameters:** Altitude, speed, and corridor width can be customized individually for each waypoint.
* **SORA Demographic Analysis:** Automatic determination of the average population density in the Adjacent Area (AA) and the maximum population density in the Ground Risk Buffer (GRB) for precise risk assessment.
* **VLOS Calculator & Visualization:** Automatic calculation and display of the ALOS/DLOS range around the pilot's position.
* **Multilingual:** Full support for German (DE) and English (EN).
* **Extensive Exports:** Supports KML, .dipul (DIPUL standard), SkyDemon (.flightplan), GeoJSON, and automated SORA Word documents (.docx) including map clippings.

---

## License & Terms of Use

### 1. Private & Non-Commercial Use
The use of this plugin for **private, academic, and non-commercial purposes** is completely **free of charge**. You are allowed to adapt the code for your private use.

### 2. Commercial Use (Companies / Public Authorities)
* **Trial Period:** Commercial users are allowed to test and evaluate the plugin free of charge for a period of **1 month**.
* **After the Trial Period:** For permanent commercial use, please contact the author at **tim.strohbach [at] gmx.de** for appropriate licensing.

### 3. Disclaimer of Warranty
The software is provided "as-is" without warranty of any kind. The author assumes no liability for the correctness of the calculations or any damage occurring during operations.

---

*Developed with ❤️ for the UAS community.*
