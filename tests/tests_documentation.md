# Dokumentation der BufferCalculator Unit-Tests (Revision 1.8 / Leitfaden 1.9)

Dieses Dokument beschreibt die mathematischen Testfälle (Unit Test Cases TC1 bis TC8) zur Verifikation der Puffer-Berechnungen (Flight Geography, Contingency Volume, Ground Risk Buffer und Adjacent Area) des Drone Corridor Planner Plugins. Alle Testfälle basieren auf den offiziellen Formeln des LBA-Leitfadens zur Dimensionierung (Revision 1.8 vom 23.09.2025).

Die Testumgebung ist als eigenständiges Testpaket im Ordner `tests` strukturiert, um die Portabilität und Weiterentwicklung mit Antigravity auf jedem System zu gewährleisten.

---

## Parameter-Matrix der Testfälle

| Zeile / Parameter | TC1 | TC2 | TC3 | TC4 | TC5 | TC6 | TC7 | TC8 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Beschreibung** | Fixed-Wing, Baro, Para CV, Para GRB | Multikopter, Baro, Def CV, Ballistic GRB | Fixed-Wing, GPS, Def CV, 1:1 GRB | Fixed-Wing, Baro, Def CV, Glide GRB | Multikopter, GPS, Para CV, Ballistic GRB | Fixed-Wing, GPS, Para CV, Glide GRB | Multikopter, Baro, Def CV, 1:1 GRB | Fixed-Wing, Baro, Def CV, Para GRB |
| **uas_type** | `FixedWing` | `Multikopter` | `FixedWing` | `FixedWing` | `Multikopter` | `FixedWing` | `Multikopter` | `FixedWing` |
| **altimetry** | `Baro` | `Baro` | `GPS` | `Baro` | `GPS` | `GPS` | `Baro` | `Baro` |
| **maxVelocity (v0)** | `20.0 m/s` | `10.0 m/s` | `20.0 m/s` | `20.0 m/s` | `12.0 m/s` | `15.0 m/s` | `15.0 m/s` | `25.0 m/s` |
| **maxCharacteristicDimension (CD)**| `3.6 m` | `1.5 m` | `3.6 m` | `3.6 m` | `2.0 m` | `4.0 m` | `2.5 m` | `4.5 m` |
| **reactionTime (tRZ)** | `1.0 s` | `1.0 s` | `1.0 s` | `1.0 s` | `1.0 s` | `1.0 s` | `1.0 s` | `1.0 s` |
| **gpsInaccuracy (SGPS)** | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` |
| **positionError (SPos)** | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` | `3.0 m` |
| **mapError (SK)** | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` |
| **altitudeErrorGps** | `4.0 m` | `4.0 m` | `4.0 m` | `4.0 m` | `4.0 m` | `4.0 m` | `4.0 m` | `4.0 m` |
| **altitudeErrorBarometric** | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` | `1.0 m` |
| **lateralContingencyManoeuvreType**| `Parachute`| `Default` | `Default` | `Default` | `Parachute`| `Parachute`| `Default` | `Default` |
| **maxRollAngle (Φ)** | `30.0 °` | `—` | `30.0 °` | `30.0 °` | `—` | `—` | `—` | `40.0 °` |
| **maxPitchAngle (Θ)** | `—` | `45.0 °` | `—` | `—` | `30.0 °` | `—` | `25.0 °` | `—` |
| **parachuteOpeningTimeLateral** | `2.0 s` | `—` | `—` | `—` | `2.5 s` | `2.0 s` | `—` | `—` |
| **verticalContingencyManoeuvreType**| `Parachute`| `Default` | `Default` | `Default` | `Parachute`| `Parachute`| `Default` | `Default` |
| **parachuteOpeningTimeVertical** | `2.0 s` | `—` | `—` | `—` | `1.5 s` | `2.0 s` | `—` | `—` |
| **groundRiskBufferMethod** | `Parachute`| `Ballistic`| `Simplified`| `Glide` | `Ballistic`| `Glide` | `Simplified`| `Parachute`|
| **glideRatioDenominator (E)** | `—` | `—` | `—` | `15.0 : 1` | `—` | `8.0 : 1` | `—` | `—` |
| **parachuteOpeningTimeGRB** | `1.0 s` | `—` | `—` | `—` | `—` | `—` | `—` | `1.5 s` |
| **maxWindVelocity (vWind)** | `3.0 m/s` | `—` | `—` | `—` | `—` | `—` | `—` | `5.0 m/s` |
| **parachuteDescentRate (vZ)** | `2.0 m/s` | `—` | `—` | `—` | `—` | `—` | `—` | `3.0 m/s` |
| **corridorWidth (W_FG)** | `50.0 m` | `50.0 m` | `50.0 m` | `50.0 m` | `60.0 m` | `80.0 m` | `50.0 m` | `100.0 m` |
| **maxFlightHeight (H_FG)** | `110.0 m` | `100.0 m` | `110.0 m` | `110.0 m` | `120.0 m` | `100.0 m` | `90.0 m` | `120.0 m` |
| **Zusätzlicher Fehler (lat / vert)**| `0.0 m` | `0.0 m` | `0.0 m` | `0.0 m` | `0.0 m` | `0.0 m` | `0.0 m` | `0.0 m` |
| **Erwartungswert R_FG** | **`25.0 m`** | **`25.0 m`** | **`25.0 m`** | **`25.0 m`** | **`30.0 m`** | **`40.0 m`** | **`25.0 m`** | **`50.0 m`** |
| **Erwartungswert R_CV** | **`92.0 m`** | **`47.0968 m`**| **`122.6239 m`**| **`122.6239 m`**| **`79.0 m`** | **`92.0 m`** | **`71.5930 m`**| **`157.9272 m`**|
| **Erwartungswert R_GRB** | **`341.5 m`** | **`95.8650 m`**| **`264.6563 m`**| **`2181.1101 m`**| **`145.2448 m`**| **`1176.0 m`** | **`185.8108 m`**| **`458.1158 m`**|
| **Erwartungswert R_AGA (AA)** | **`5092.0 m`**| **`5047.0968 m`**| **`5122.6239 m`**| **`5122.6239 m`**| **`5079.0 m`** | **`5092.0 m`** | **`5071.5930 m`**| **`5157.9272 m`**|

---

## Formeln & Berechnungsherleitung (Erläuterung)

* **R_FG (Flight Geography Radius):**
  $$R_{FG} = \frac{W_{FG}}{2}$$ (wenn größer als $3 \times CD$).

* **R_CV (Contingency Volume Radius):**
  $$R_{CV} = R_{FG} + S_{GPS} + S_{Pos} + S_K + (v_0 \times t_{RZ}) + S_{CM}$$
  * *Lateral Standard (Kurve, Fixed-Wing):* $S_{CM} = \frac{v_0^2}{g \times \tan(\Phi)}$
  * *Lateral Standard (Stop, Multikopter):* $S_{CM} = \frac{0.5 \times v_0^2}{g \times \tan(\Theta)}$
  * *Lateral Fallschirm:* $S_{CM} = v_0 \times t_{para\_lat}$

* **h_cv (Contingency Volume Ceiling Height):**
  $$h_{cv} = H_{FG} + H_{\Delta} + (0.7 \times v_0 \times t_{RZ}) + h_{CM}$$
  * *Vertikal Standard (Climb, Fixed-Wing):* $h_{CM} = \frac{0.3 \times v_0^2}{g}$
  * *Vertikal Standard (Energy conversion, Multikopter):* $h_{CM} = \frac{0.5 \times v_0^2}{g}$
  * *Vertikal Fallschirm:* $h_{CM} = 0.7 \times v_0 \times t_{para\_vert}$

* **R_GRB (Ground Risk Buffer Radius):**
  $$R_{GRB} = R_{CV} + S_{GRB}$$
  * *Simplified (1:1):* $S_{GRB} = h_{cv} + 0.5 \times CD$
  * *Ballistic:* $S_{GRB} = v_0 \times \sqrt{\frac{2 \times h_{cv}}{g}} + 0.5 \times CD$
  * *Glide:* $S_{GRB} = h_{cv} \times E$
  * *Parachute:* $S_{GRB} = v_0 \times t_{para\_grb} + \frac{v_{wind} \times h_{cv}}{v_Z}$

* **R_AGA / R_AA (Adjacent Ground Area / Adjacent Area):**
  $$R_{AGA} = R_{CV} + S_{AGA}$$
  * wobei $S_{AGA} = \max(5000, \min(35000, 180 \times v_{max}))$ mit $v_{max} = v_0$ im Standardbetrieb.
