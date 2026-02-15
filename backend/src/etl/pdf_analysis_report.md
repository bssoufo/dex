# PDF Structure Analysis Report

**Generated:** 2026-02-15
**Purpose:** Guide extraction template development for Plans 02-02 and 02-03

## Summary

All 3 manufacturer PDFs were successfully downloaded and analyzed. Key finding:
spec data is organized very differently across manufacturers, confirming the need
for per-manufacturer extraction templates.

| Manufacturer | PDF | Pages | Pages with Tables | Text Selectable |
|---|---|---|---|---|
| Sundance | 880-series-2026.pdf (24.4 MB) | 92 | 14 | Yes |
| Hot Spring | highlife-2026.pdf (4.2 MB) | 46 | 12 | Yes |
| Bullfrog | m-series.pdf (11.0 MB, 2025 version) | 46 | 10 | Yes |

All three PDFs have fully selectable text (pdfplumber extracts text successfully).
No scanned/image-only pages detected.

---

## Sundance 880 Series (880-series-2026.pdf)

### Overview
- **Total pages:** 92
- **File size:** 24.4 MB
- **Models covered:** Aspen, Optima, Cameo, Altamar, Vistamar, Marin, Capri
- **Layout:** Owner's manual format. No single spec comparison table. Specs are
  distributed across per-model feature pages and an electrical requirements page.

### Spec Data Locations

| Spec Category | Pages | Format | Notes |
|---|---|---|---|
| Jet pumps | 22, 90-92 | Text + wiring diagram tables | Page 22 has pump system configs (1/2/3-pump, amperage). Pages 90-92 have wiring diagrams with pump voltage/amperage. Pump count varies by model (1-3 pumps). |
| Circulation pump | 20-21 | Equipment diagram | Equipment location diagrams reference circulation pump. Details are sparse in text. |
| Spa pak | 20-21, 90-92 | Equipment diagram + wiring | Control board shown in equipment diagrams. Wiring diagrams on pages 90-92 reference the circuit board. |
| Topside control | 49-70 | Text sections | SmartTub touchscreen control documented extensively. Registration and control operations. |
| Jets | 28-48 | Per-model feature diagrams | **Key pages.** Each model has its own feature page listing jet types and counts (e.g., Aspen page 28: Fluidix ST 16 ea., Fluidix Nex 8 ea., Focus 6 ea., etc.). Per-model pages: Aspen 28-30, Optima 31-33, Cameo 34-36, Altamar 37-39, Vistamar 40-42, Marin 43-45, Capri 46-48. |
| Headrests | 28-48 | Per-model feature diagrams | Listed as "Pillows" in feature diagrams (e.g., Aspen: Pillows 4 ea.). |
| Filters | 74-76 | Maintenance section | Filter cartridge maintenance and replacement info. MicroClean Ultra filtration system mentioned. |
| Heater | 62, 86-87 | Temperature settings + troubleshooting | Page 62 covers heat settings. Pages 86-87 reference heater errors/authentication. |
| Lighting | 28-48 | Per-model feature diagrams | Each model lists lights (e.g., "Lights 2 ea.", "LED Light Lenses"). |
| Cover | Not found | N/A | Cover dimensions not in this manual. Will need web scraping (Phase 3). |

### Electrical Requirements (Page 22)

Extracted table structure:
```
North American 60 Hz
Voltage:          240 VAC (all configs)
Max Current Draw:
  1-Pump System:  28A / 39A / N/A
  2-Pump System:  28A / 39A / 48A
  3-Pump System:  N/A / 39A / 48A
Circuit Breaker:  40A / 50A / 60A (2-Pole)
```

### Per-Model Feature Pages (Critical for extraction)

Each model gets a 2-3 page spread with:
1. **Feature diagram** -- labeled illustration showing jet types, pillow count, lights,
   waterfall, air controls, etc. with quantities (e.g., "Fluidix ST Jets (16 ea.)")
2. **Massage/Waterfall Selector diagram** -- shows pump-to-jet zone mapping
3. **Air Controls diagram** -- shows air control assignments

Model page ranges:
- Aspen: pages 28-30
- Optima: pages 31-33
- Cameo: pages 34-36
- Altamar: pages 37-39
- Vistamar: pages 40-42
- Marin: pages 43-45
- Capri: pages 46-48

### Wiring Diagrams (Pages 90-92)

Page 92 contains a device table with pump connections:
```
J9:  1-SP Pump 1    240V  11A Max
J14: 1-SP Pump 2 + 1-SP Pump 3   240V  11A Max + 11A Max
J50: Spa Light     10V   2A
J21: Blower        240V  4A Max
```
Also includes dip switch settings table (page 92) for breaker configuration.

### Extraction Strategy for Sundance

1. **Jets, headrests, lighting:** Extract from per-model feature pages (28-48).
   Claude's vision capability is ideal here since jet counts are in labeled diagrams.
2. **Jet pumps, electrical:** Combine page 22 (electrical requirements) with
   pages 90-92 (wiring diagrams). Number of pumps per model determined from
   massage selector diagrams (pages 29, 32, 35, 38, 41, 44, 47).
3. **Filters, heater:** Pages 74-76 and 62. Likely series-shared specs.
4. **Topside control:** Pages 49-55. SmartTub system is series-shared.
5. **Cover:** Not in manual. Mark as null, fill from website in Phase 3.

### Layout Observations
- Text is well-structured but specs are NOT in tabular comparison format
- Feature diagrams are visual with labeled callouts -- Claude PDF vision is essential
- Wiring diagram tables on pages 90-92 use line-based tables (pdfplumber extracts them)
- The manual is large (92 pages) -- use page hints to target relevant sections

---

## Hot Spring Highlife Collection (highlife-2026.pdf)

### Overview
- **Total pages:** 46
- **File size:** 4.2 MB
- **Models covered:** Grandee, Envoy, Vanguard, Aria, Sovereign, Prodigy, Jetsetter LX, Jetsetter
- **Layout:** Compact owner's manual. Has a **single spec comparison table on page 45**
  (the most extraction-friendly format of all 3 manufacturers).

### Spec Data Locations

| Spec Category | Pages | Format | Notes |
|---|---|---|---|
| Jet pumps | 25-32 | Per-model jet diagrams | Each model has its own page showing jet pump assignments (Pump 1 System 1, Pump 1 System 2, etc.) with jet types per zone. |
| Circulation pump | 41-42 | Troubleshooting text | SilentFlo 5000 circulation pump referenced in service section. |
| Spa pak | 7, 46 | Feature overview + back cover | IQ 2020 control system mentioned. Page 46 lists model numbers. |
| Topside control | 17-24 | Control panel guide | Detailed touch screen control documentation. |
| Jets | 25-32 | Per-model jet diagrams | **Key pages.** Each model has a diagram showing jet types by zone: Moto-Massage DX, SmartJet, HydroStream, HighFlow, Rotary Hydromassage, Directional Hydromassage, etc. |
| Headrests | 7 | Feature overview | "Comfort Pillow" referenced in spa features overview. |
| Filters | 34, 45 | Maintenance + spec table | Tri-X filter system. Page 45 spec table has filter area in sq ft. |
| Heater | 14-15, 45 | Maintenance + spec table | No-Fault heater. Page 45 has heater wattage per model. |
| Lighting | 7 | Feature overview | LED lighting mentioned in features. |
| Cover | 45 | Spec table | Dimensions on page 45 (footprint, height). |

### Master Spec Table (Page 45) -- CRITICAL

Page 45 contains a single comparison table for all 8 models with columns:
- Spa Model (with model code and seating capacity)
- Footprint Dimensions
- Height
- Effective Filter Area (sq ft)
- Heater Watts
- Water Capacity (gallons/liters)
- Dry Weight
- Filled Weight
- Dead Weight (load per sq ft)
- Electrical Requirements

Extracted data (pdfplumber successfully parses this table):
```
Grandee (GGN) 7 seats:  100"x91", 38", 325 sqft, 4000W, 455 gal, 230V 20A+30A
Envoy (KKN) 5 seats:    100"x91", 38", 325 sqft, 4000W, 455 gal, 230V 20A+30A
Vanguard (VVN) 6 seats:  87"x87", 36", 325 sqft, 4000W, 375 gal, 230V 20A+30A
Aria (ARN) 5 seats:      87"x87", 36", 325 sqft, 4000W, 365 gal, 230V 20A+30A
Sovereign (IIN) 5 seats:  80"x93", 33", 195 sqft, 6000W, 330 gal, 230V 20A+30A
Prodigy (HN) 5 seats:    84"x78", 33", 195 sqft, 1500/6000W, 270 gal, 230V 20A+30A
Jetsetter LX (JTN) seats: 84"x68", 33", 195 sqft, 6000W, 250 gal, 230V 20A+30A
Jetsetter (JJN) 3 seats:  84"x68", 33", 195 sqft, 1500/6000W, 245 gal, 115V/230V
```

### Per-Model Jet Diagrams (Pages 25-32)

Each model has a full-page diagram showing:
- Jet pump assignments (which pump powers which jet system)
- Jet types per zone with SmartJet lever positions
- Named jet types: Moto-Massage DX, SmartJet, HydroStream, HighFlow,
  Rotary Hydromassage, Directional Hydromassage, Directional Precision

Model pages:
- Grandee: page 25
- Envoy: page 26
- Vanguard: page 27
- Aria: page 28
- Sovereign: page 29
- Prodigy: page 30
- Jetsetter LX: page 31
- Jetsetter: page 32

### Extraction Strategy for Hot Spring

1. **Dimensions, heater, filter area, electrical, seating:** Extract from page 45
   spec table. pdfplumber successfully parses this table with line-based strategy.
2. **Jets:** Extract from per-model jet diagrams (pages 25-32). Claude vision needed
   to read labeled diagrams. Cross-reference with page 45 for validation.
3. **Jet pumps:** Extract from per-model jet diagrams which show pump assignments.
4. **Circulation pump, topside control:** Pages 7, 17-24, 41-42. Likely series-shared.
5. **Cover:** Derive from page 45 footprint dimensions.

### Layout Observations
- Most extraction-friendly of the 3 manufacturers
- Page 45 spec table is clean, well-structured, pdfplumber-parseable
- Per-model jet diagrams are visual but consistently formatted
- Compact manual (46 pages) -- reasonable to send full PDF with page hints
- Some models have dual electrical options (Jetsetter: 115V or 230V)

---

## Bullfrog M Series (m-series.pdf)

### Overview
- **Total pages:** 46
- **File size:** 11.0 MB
- **PDF version:** 2025 (2026 not yet published)
- **Models covered:** M9, M8, M7, M6
- **Layout:** Owner's manual. Specs distributed across feature overview,
  equipment compartment diagrams, and installation sections. Dimensions
  table on page 32.

### Spec Data Locations

| Spec Category | Pages | Format | Notes |
|---|---|---|---|
| Jet pumps | 9, 12, 37 | Equipment diagram + control guide + wiring | Page 9 shows equipment compartment with Jet pump 1/2/3 labeled. Page 12 mentions M9/M8 have 3 jet pumps. Page 37 has wiring diagram with pump voltage/speed details. |
| Circulation pump | 9, 37 | Equipment diagram + wiring | "Circulation pump / O3" labeled in equipment compartment and wiring diagram. 240V, 2-speed (low speed K1, common L2). |
| Spa pak | 9 | Equipment diagram | "Control center box" shown in equipment compartment. |
| Topside control | 12-16 | Control guide | "Premium Touch Screen Control (K1000)" for M9/M8. Detailed control operation documentation. |
| Jets | 8, 17 | Feature overview + JetPak guide | **Critical:** Bullfrog uses modular JetPak system. Page 8 shows spa overview with JetPaks, in-wall therapy jets, high-flow foot therapy jet, leg therapy jets. Page 17 covers JetPak interchanging. |
| Headrests | 8 | Feature overview | "Adjustable headrest" listed in spa overview (item 4). |
| Filters | 8, 28 | Feature overview + maintenance | "Filter access" and "Simplicity Filter" mentioned. Page 28 winterization references filter cleaning. |
| Heater | 9 | Equipment diagram | "Water heater" shown in equipment compartment. |
| Lighting | 8 | Feature overview | "Interior LED lights" listed in spa overview. |
| Cover | 32 | Dimensions table | Cover dimensions derivable from spa dimensions table. |

### Dimensions Table (Page 32) -- CRITICAL

pdfplumber successfully extracts this table:
```
Model | Width         | Length        | Height
M9    | 7'10" (2.39m) | 9'2" (2.80m) | 38" (.97m)
M8    | 7'10" (2.39m) | 7'10" (2.39m)| 38" (.97m)
M7    | 7'7" (2.31m)  | 7'7" (2.31m) | 37" (.94m)
M6    | 6'8" (2.03m)  | 7'7" (2.31m) | 34" (.86m)
```

### Equipment Compartment (Page 9)

Labeled diagram showing physical layout of:
- Jet pump 1, 2, 3 (positions labeled)
- Control center box
- Ozone / AOP
- EOS mixing module
- Water heater
- Filter weir and intake assembly
- Audio control box
- Pump access hinge assembly
- External Air Bleeder

### Wiring Diagram (Page 37)

YT-9 UL Wiring Diagram for M Series (North America 60 Hz):
```
Pump 1 (A2): 240V, 2-speed (low K6, high K3)
Pump 2 (A3): 240V, 2-speed (low K2, high K4)
Pump 3 (C1): 240V, 2-speed (low K22, high K23)
Circulation pump / O3 (A1): 240V (low K1, common L2)
Waterfall Pump (C2): 240V
External light (C3): 240V
```

### Electrical Requirements (Page 33-34)

240V/60Hz permanently-connected spas require:
- GFCI protected, 4-wire, 240V/60Hz, 50A or 60A
- Single-phase, dedicated electrical circuit

### JetPak System Notes

The Bullfrog JetPak system is fundamentally different from Sundance/Hot Spring:
- JetPaks are interchangeable cartridges that slot into bays
- Number of JetPak bays varies by model (M9 has the most)
- Each JetPak has different jet configurations
- The manual does NOT list total jet counts per model -- this depends on
  which JetPaks are installed
- Page 17 covers JetPak interchanging procedure
- Individual JetPak specifications are likely on the Bullfrog website, not in
  this owner's manual

### Extraction Strategy for Bullfrog

1. **Dimensions:** Extract from page 32 table. pdfplumber handles this well.
2. **Jet pumps:** Combine page 9 (equipment diagram), page 12 (M9/M8 have 3 pumps),
   and page 37 (wiring with voltage/speed). Need to determine pump count per model
   (M9/M8: 3 pumps, M7/M6: likely fewer -- need Claude vision for this).
3. **Jets:** This is the most complex extraction. Mark as modular_jetpak system type.
   Extract JetPak bay count and available JetPak options from the manual. Detailed
   JetPak specs will need Phase 3 web scraping from bullfrogspas.com.
4. **Other categories:** Mostly series-shared. Extract from feature overview (page 8)
   and equipment diagram (page 9).
5. **Note:** This is the 2025 manual. Record year mismatch in source references.

### Layout Observations
- More visual/diagram-heavy than the other two manufacturers
- Equipment compartment diagrams are key for identifying components
- JetPak modular system means jet extraction is fundamentally different
- Wiring diagram (page 37) is the most detailed pump spec source
- Dimensions table is clean and pdfplumber-parseable
- Some pages have multi-column layout (water care sections)
- 2025 version -- 2026 manual not yet published by Bullfrog

---

## Cross-Manufacturer Comparison

### Data Availability by Category

| Category | Sundance | Hot Spring | Bullfrog |
|---|---|---|---|
| Jet pumps | Good (pages 22, 90-92) | Good (pages 25-32) | Good (pages 9, 37) |
| Circulation pump | Limited | Good (SilentFlo 5000) | Good (page 9, 37) |
| Spa pak | Limited | Good (IQ 2020) | Limited |
| Topside control | Good (SmartTub) | Good (pages 17-24) | Good (K1000, pages 12-16) |
| Jets | Good (per-model, pages 28-48) | Good (per-model, pages 25-32) | Complex (modular JetPak) |
| Headrests | Good (per-model feature pages) | Limited | Limited |
| Filters | Moderate (pages 74-76) | Good (page 45 filter area) | Limited |
| Heater | Limited | Good (page 45 wattage) | Limited |
| Lighting | Good (per-model feature pages) | Limited | Limited |
| Cover | Not in manual | Derivable (page 45) | Derivable (page 32) |
| Dimensions | Not in manual | Good (page 45) | Good (page 32) |
| Electrical | Good (page 22) | Good (page 45) | Good (pages 33-34) |
| Seating capacity | Per-model feature pages | Good (page 45) | Not in manual |

### Key Insights

1. **Hot Spring is the easiest to extract** -- single spec table on page 45 plus
   consistent per-model jet diagrams. Most data in structured format.

2. **Sundance has the most distributed data** -- no central spec table. Must
   assemble specs from 92 pages of manual. Per-model feature diagrams (pages 28-48)
   are the primary data source. Claude vision is essential for reading labeled diagrams.

3. **Bullfrog is architecturally different** -- JetPak modular system means jet
   extraction requires different logic. Manual has good pump/dimension data but
   jet details are minimal (by design -- configurations are customer-chosen).

4. **All PDFs have selectable text** -- pdfplumber text extraction works on all pages.
   No OCR issues detected.

5. **Cover dimensions missing from Sundance** -- will need Phase 3 web scraping.

6. **Part numbers are sparse in all manuals** -- owner's manuals focus on operation,
   not service parts. Part numbers will primarily come from Phase 3 web scraping or
   manual entry in Phase 4.

7. **Bullfrog manual is 2025 version** -- no 2026 version published yet. Source
   references must note this year mismatch.

### Extraction Priority

Given the analysis, recommended extraction order for Plans 02-02 and 02-03:
1. **Hot Spring** first (most structured data, page 45 spec table)
2. **Sundance** second (most data available, but distributed across feature pages)
3. **Bullfrog** third (least spec detail in manual, depends on web scraping for jets)

---

## Technical Notes

### pdfplumber Table Extraction Results

- **Line-based strategy works well** for: Hot Spring page 45, Bullfrog page 32,
  Sundance pages 90-92
- **Text-based strategy needed** when lines aren't present (some Sundance pages)
- **Table settings used:** `vertical_strategy="lines"`, `horizontal_strategy="lines"`,
  `snap_tolerance=3`
- Merged cells in Hot Spring page 45 spec table cause multi-line cell content
  (e.g., dimensions split across lines with metric conversion)

### Claude PDF API Considerations

- Sundance at 92 pages / 24.4 MB is the largest. May benefit from page-range targeting.
- Hot Spring at 46 pages / 4.2 MB is compact enough for full-PDF submission.
- Bullfrog at 46 pages / 11.0 MB is moderate.
- **Prompt caching recommended** for all -- each PDF will be queried multiple times
  across models and categories.

### File Hashes (for provenance tracking)

Record these when building SourceReference metadata:
- Sundance: 880-series-2026.pdf (24,983,552 bytes)
- Hot Spring: highlife-2026.pdf (4,310,016 bytes)
- Bullfrog: m-series.pdf (11,261,952 bytes, 2025 version v1.1)
