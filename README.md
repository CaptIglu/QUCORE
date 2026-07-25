# QUCORE – Flexible Drohnenflugplanung in QGIS (FG, CV, GRB & AA)

🇩🇪 **Deutsch** | 🇬🇧 [**English Version**](#english-version)

**QUCORE** (<u>Q</u>GIS <u>U</u>AS <u>C</u>orridor <u>O</u>utlining & <u>R</u>outing <u>E</u>ngine) ist ein professionelles, SORA-konformes QGIS-Plugin zur interaktiven Planung von UAS-Flugkorridoren. Es berechnet dynamisch und in Echtzeit die **Flight Geography (FG)**, das **Contingency Volume (CV)** und den **Ground Risk Buffer (GRB)** basierend auf offiziellen Leitlinien der EASA und des LBA.

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
* **Asymmetrische Pufferberechnung über Wind-Drift:** Optional: Asymmetrische GRB Berechnung über min/max Windstärke und Windrichtung.
* **SORA-Demografie-Analyse:** Automatische Ermittlung der durchschnittlichen Bevölkerungsdichte im Adjacent Area (AA) sowie Angabe der maximalen Bevölkerungsdichte im Ground Risk Buffer (GRB) zur präzisen Risikobewertung.
* **VLOS-Rechner & Visualisierung:** Automatische Berechnung und Anzeige der ALOS/DLOS-Reichweite um die Pilotenposition.
* **Multilingual:** Volle Unterstützung für Deutsch (DE) und Englisch (EN).
* **Umfangreiche Dateischnittstellen (Import/Export):** Unterstützt KML, .dipul (DIPUL-Standard), SkyDemon (.flightplan), QGroundControl (.plan), MissionPlanner / Ardupilot (.waypoints), GeoJSON, GeoPackage und automatisierte SORA-Word-Dokumente (.docx) inklusive Kartenausschnitt.

---

## Lizenz & Commercial Supporter Modell

### 1. Freie Open-Source Lizenz (GPLv2+)
QUCORE ist freie Open-Source-Software, lizenziert unter der **GNU General Public License v2.0 oder neuer (GPL-2.0-or-later)**.

### 2. Commercial Supporter License (Empfehlung für gewerbliche Nutzer)
Wenn Sie oder Ihr Unternehmen QUCORE kommerziell nutzen und einen geschäftlichen Mehrwert daraus ziehen, bitten wir Sie herzlich, QUCORE als **Commercial Supporter** zu unterstützen.
* **Gültigkeit:** Gilt jeweils für die gesamte **Major-Version** .
* **Erwerb & Aktivierung:** Kontaktieren Sie den Autor unter **tim.strohbach  [at] gmx.de** für eine Rechnung und Ihren Freischaltschlüssel. Der Schlüssel entfernt den Hinweistext und schaltet den Status *"Registrierter Commercial Supporter"* frei.

### 3. Flugsicherheit & Gewährleistungsausschluss
> **Wichtiger Hinweis:** QUCORE dient als Unterstützungswerkzeug für die Flugplanung. Die berechneten SORA-Puffer entbinden den Fernpiloten und Betreiber nicht von der eigenverantwortlichen Prüfung und Einhaltung aller gesetzlichen Vorgaben der Luftfahrtbehörden (EASA/LBA). **Nutzung auf eigene Gefahr. Keine Gewährleistung für die Richtigkeit der berechneten Geodaten.**


<a id="english-version"></a>
# QUCORE – QGIS variable drone flight planning of FG, CV & GRB (English)

**QUCORE** (<u>Q</u>GIS <u>U</u>AS <u>C</u>orridor <u>O</u>utlining & <u>R</u>outing <u>E</u>ngine) is a professional, SORA-compliant QGIS plugin for interactive planning of UAS flight corridors. It calculates the **Flight Geography (FG)**, the **Contingency Volume (CV)**, and the **Ground Risk Buffer (GRB)** dynamically and in real time based on official EASA and LBA guidelines.

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
* **Asymmetric buffer calculation based on wind drift:** Optional: Asymmetric GRB calculation based on minimum/maximum wind speed and wind direction.
* **SORA Demographic Analysis:** Automatic determination of the average population density in the Adjacent Area (AA) and the maximum population density in the Ground Risk Buffer (GRB) for precise risk assessment.
* **VLOS Calculator & Visualization:** Automatic calculation and display of the ALOS/DLOS range around the pilot's position.
* **Multilingual:** Full support for German (DE) and English (EN).
* **Extensive File Interfaces (Import/Export):** Supports KML, .dipul (DIPUL standard), SkyDemon (.flightplan), QGroundControl (.plan), MissionPlanner / Ardupilot (.waypoints), GeoJSON, GeoPackage, and automated SORA Word documents (.docx) including map clippings.

---

## License & Commercial Supporter Model

### 1. Free Open-Source License (GPLv2+)
QUCORE is free open-source software licensed under the **GNU General Public License v2.0 or later (GPL-2.0-or-later)**. 

### 2. Commercial Supporter License (Recommended for Commercial Users)
If you or your company use QUCORE commercially and derive value from it, we kindly invite you to support as a **Commercial Supporter**.
* **Validity:** Valid for the entire **Major Version** release cycle.
* **Purchase & Activation:** Contact the author at **tim.strohbach  [at] gmx.de** to receive an invoice and your supporter key. Entering the key removes the reminder banner and unlocks the *"Registered Commercial Supporter"* status.

### 3. Aviation Safety & Disclaimer
> **Important Notice:** QUCORE serves as a planning support tool. SORA buffer calculations do not exempt remote pilots or operators from independent verification and full compliance with aviation regulations (EASA/LBA). **Use at your own risk. No warranty for the accuracy of calculated spatial data.**

---

*Developed with ❤️ for the UAS community.*
