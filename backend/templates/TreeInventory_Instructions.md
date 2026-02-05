# Tree Inventory CSV Template - Instructions

## Download Template
Use the provided **TreeInventory_Template.csv** file as your starting point.

---

## Required Columns

### 1. **species** (Required)
- **Description**: Scientific name or local name of tree species
- **Format**: Text
- **Examples**:
  - `Shorea robusta` (scientific name)
  - `Sal` (local name - will be auto-matched)
  - `Schima wallichii`
  - `Chilaune`

**Supported Species:**
- Shorea robusta (Sal)
- Schima wallichii (Chilaune)
- Dalbergia sissoo (Sissoo)
- Pinus roxburghii (Khote Salla)
- Acacia catechu (Khayar)
- And 20+ more species...

---

### 2. **dia_cm** (Required)
- **Description**: Diameter at Breast Height (DBH) in centimeters
- **Format**: Number (decimal allowed)
- **Unit**: Centimeters (cm)
- **Range**: 1 - 150 cm (typical)
- **Examples**:
  - `45.5` (45.5 cm diameter)
  - `32.0` (32 cm diameter)

**Important Notes:**
- ⚠️ Use **DIAMETER**, not girth/circumference
- ⚠️ If you have girth (GBH), the system will auto-detect and convert
- ⚠️ Do not include units in the value (just the number)
- ⚠️ Use period (.) for decimals, not comma (,)

**Alternative Column Names (also accepted):**
- `diameter`, `dbh`, `DBH`, `dia`, `diam`

---

### 3. **height_m** (Required)
- **Description**: Total tree height in meters
- **Format**: Number (decimal allowed)
- **Unit**: Meters (m)
- **Range**: 1.3 - 45 m (typical for Nepal)
- **Examples**:
  - `25.3` (25.3 meters tall)
  - `18.5` (18.5 meters tall)

**Important Notes:**
- ⚠️ For seedlings (DBH < 10 cm), height will be ignored/estimated
- ⚠️ Use total height, not merchantable height
- ⚠️ Use period (.) for decimals, not comma (,)

**Alternative Column Names (also accepted):**
- `height`, `tree_height`, `ht`, `Height_m`

---

### 4. **class** (Optional)
- **Description**: Tree quality class
- **Format**: Single letter
- **Values**:
  - `A` = Good quality (straight, healthy, no defects)
  - `B` = Medium quality (minor defects)
  - `C` = Poor quality (major defects, hollow, diseased)
- **Default**: If not provided, system assigns based on DBH

**Alternative Column Names (also accepted):**
- `tree_class`, `quality_class`, `Class`

---

### 5. **LONGITUDE** (Required)
- **Description**: Geographic longitude coordinate
- **Format**: Decimal degrees
- **Unit**: Degrees (°)
- **Range**: 80.0 to 88.3 (Nepal bounds)
- **Examples**:
  - `85.3240` (East longitude)
  - `84.1234`

**Important Notes:**
- ⚠️ Use **DECIMAL DEGREES**, not Degrees-Minutes-Seconds
- ⚠️ Nepal is in Eastern Hemisphere (positive values)
- ⚠️ Use period (.) for decimals, not comma (,)
- ⚠️ At least 4 decimal places recommended for accuracy (~10m precision)

**Alternative Column Names (also accepted):**
- `longitude`, `long`, `lon`, `lng`, `x`, `X`, `easting`

---

### 6. **LATITUDE** (Required)
- **Description**: Geographic latitude coordinate
- **Format**: Decimal degrees
- **Unit**: Degrees (°)
- **Range**: 26.3 to 30.5 (Nepal bounds)
- **Examples**:
  - `27.7172` (North latitude)
  - `28.3456`

**Important Notes:**
- ⚠️ Use **DECIMAL DEGREES**, not Degrees-Minutes-Seconds
- ⚠️ Nepal is in Northern Hemisphere (positive values)
- ⚠️ Use period (.) for decimals, not comma (,)
- ⚠️ At least 4 decimal places recommended for accuracy (~10m precision)

**Alternative Column Names (also accepted):**
- `latitude`, `lat`, `y`, `Y`, `northing`

---

## Coordinate Reference System (CRS)

### Supported CRS:
1. **EPSG:4326** - WGS84 Geographic (Lat/Lon in decimal degrees) ✅ **Recommended**
2. **EPSG:32644** - UTM Zone 44N (Western Nepal, easting/northing in meters)
3. **EPSG:32645** - UTM Zone 45N (Eastern Nepal, easting/northing in meters)

### Auto-Detection
- System will **automatically detect** your CRS based on coordinate values
- If uncertain, you can specify EPSG code during upload

### Example Coordinates by CRS:

**Geographic (EPSG:4326):**
```csv
LONGITUDE,LATITUDE
85.3240,27.7172
```

**UTM 44N (EPSG:32644):**
```csv
x,y
456789.12,3067890.45
```

**UTM 45N (EPSG:32645):**
```csv
easting,northing
589234.56,3045678.90
```

---

## Data Preparation Guidelines

### ✅ DO:
- Use consistent units throughout the file
- Include column headers in the first row
- Use decimal points (.) for decimal numbers
- Save as CSV (UTF-8 encoding)
- Remove any summary rows (totals, averages)
- Remove completely empty rows
- Use scientific names when possible
- Record GPS coordinates with at least 4 decimal places

### ❌ DON'T:
- Mix units (e.g., some rows in cm, others in mm)
- Use commas (,) as decimal separators
- Include unit symbols in values (e.g., "45 cm" - just use "45")
- Add extra columns between required columns
- Use merged cells in Excel
- Include formulas (save as values)
- Add multiple header rows
- Use special characters in species names

---

## Common Mistakes to Avoid

### 1. Girth vs Diameter
❌ **Wrong**: Entering girth (circumference) in dia_cm column
✅ **Right**: Enter diameter only (system auto-detects girth and converts)

**Conversion**: If you have girth, divide by 3.14159
- Girth 157 cm = Diameter 50 cm

### 2. Wrong Units
❌ **Wrong**:
- Diameter in mm: `450` (should be `45`)
- Height in feet: `80` (should be `24.4`)
- Coordinates in DMS: `27°43'12"`

✅ **Right**:
- Diameter in cm: `45`
- Height in m: `24.4`
- Coordinates in decimal degrees: `27.7200`

### 3. Excel Auto-Formatting
❌ **Wrong**: Excel converts `1-2` to date `Jan-2`
✅ **Right**: Format cells as **Text** before entering data

### 4. Coordinate Swapping
❌ **Wrong**:
```csv
LONGITUDE,LATITUDE
27.7172,85.3240  (swapped!)
```
✅ **Right**:
```csv
LONGITUDE,LATITUDE
85.3240,27.7172
```

### 5. Missing Decimal Points
❌ **Wrong**: `455` (meant 45.5)
✅ **Right**: `45.5`

---

## File Saving Instructions

### From Excel:
1. Open your completed inventory file
2. Go to **File → Save As**
3. Choose **CSV UTF-8 (Comma delimited) (.csv)**
4. Click **Save**
5. If Excel warns about features, click **Yes** to continue

### From Google Sheets:
1. Open your completed inventory file
2. Go to **File → Download → Comma Separated Values (.csv)**
3. Save the downloaded file

### Encoding:
- **Always use UTF-8 encoding** to support Nepali/special characters
- If you see garbled characters (�, Ã), re-save with UTF-8

---

## Validation & Upload Process

### Step 1: Prepare Data
- Fill in the template with your tree measurements
- Follow all guidelines above

### Step 2: Upload
- Go to Inventory Upload page
- Select your CSV file
- Optionally specify CRS (if system can't auto-detect)
- Optionally specify grid spacing for mother tree selection

### Step 3: Validation
- System will automatically:
  - ✅ Check for errors (missing data, invalid values)
  - ✅ Detect column names (even if you use different names)
  - ✅ Detect if you used girth instead of diameter
  - ✅ Match species names (even with typos)
  - ✅ Auto-detect coordinate system
  - ✅ Flag outliers and suspicious values

### Step 4: Review Report
- Review the validation report
- Check warnings and auto-corrections
- Confirm or reject changes

### Step 5: Process
- System calculates:
  - Tree volumes (stem, branch, total)
  - Gross and net volumes
  - Firewood quantities
  - Mother tree selections
  - Summary statistics

---

## Example Data

### Minimal Valid File:
```csv
species,dia_cm,height_m,class,LONGITUDE,LATITUDE
Shorea robusta,45.5,25.3,A,85.3240,27.7172
Schima wallichii,32.0,18.5,A,85.3245,27.7175
```

### With Alternative Column Names:
```csv
species,dbh,height,quality_class,long,lat
Sal,45.5,25.3,A,85.3240,27.7172
Chilaune,32.0,18.5,A,85.3245,27.7175
```

### UTM Coordinates:
```csv
species,diameter,height_m,class,x,y
Shorea robusta,45.5,25.3,A,456789.12,3067890.45
```

---

## Need Help?

### Species List
- Download full species list from the system
- 25 commonly used species pre-loaded
- Contact admin to add new species

### Support
- If validation fails, system provides detailed error messages
- Each error includes:
  - Row number
  - Problem description
  - Suggested correction
  - Expected format/range

### Tips for Success
1. Start with the provided template
2. Add your data row by row
3. Keep formatting consistent
4. Save as CSV UTF-8
5. Upload and review validation report
6. Make corrections if needed
7. Re-upload if necessary

---

**Template Version**: 1.0
**Last Updated**: February 2026
**System**: Community Forest Management System
