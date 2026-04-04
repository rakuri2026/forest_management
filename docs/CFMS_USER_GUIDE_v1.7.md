# Community Forest Management System - User Guide
# समुदाय वन व्यवस्थापन प्रणाली - प्रयोगकर्ता मार्गदर्शिका

## Document Version: 1.0
## Prepared for: CFMS v1.7.0 Streamlined Workflow
## Language: English & नेपाली

---

# Table of Contents / तालिका
1. [Introduction / परिचय](#1-introduction--परचय)
2. [Workflow Overview / कार्य प्रवाह सिंहावलोकन](#2-workflow-overview--कारय-प्रवाह-सिंहावलोकन)
3. [Step-by-Step Guide / चरण-दर-चरण मार्गदर्शिका](#3-step-by-step-guide--चरण-दर-चरण-मार्गदर्शिका)
4. [Best Practices / उत्तम अभ्यासहरू](#4-best-practices--उत्तम-अभ्यासहरू)
5. [Troubleshooting / समस्या समाधान](#5-troubleshooting--समस्या-समाधान)

---

# 1. Introduction / परिचय

## 1.1 Purpose / उद्देश्य

This document provides comprehensive user guidance for the Community Forest Management System (CFMS), specifically covering the streamlined map creation workflow introduced in version 1.7.0.

यो документले समुदाय वन व्यवस्थापन प्रणाली (CFMS) को लागि व्यापक प्रयोगकर्ता मार्गदर्शिका प्रदान गर्दछ, विशेष गरी संस्करण 1.7.0 मा परिचय गराइएको सुव्यवस्थित नक्शा सिर्जना कार्यप्रवाहलाई समेट्दछ।

## 1.2 Target Users / लक्षित प्रयोगकर्ताहरू

- Community Forest User Committee (CFUC) members
- Forest officers and technicians
- GIS specialists
- समुदाय वन प्रयोगकर्ता समिति (CFUC) का सदस्यहरू
- वन अधिकारीहरू र प्राविधिकहरू
- GIS विशेषज्ञहरू

## 1.3 System Requirements / प्रणाली आवश्यकताहरू

- Modern web browser (Chrome, Firefox, Edge, Safari)
- Internet connection
- User account with login credentials
- आधुनिक वेब ब्राउजर (Chrome, Firefox, Edge, Safari)
- इन्टरनेट जडान
- लगइन प्रमाणहरू भएको प्रयोगकर्ता खाता

---

# 2. Workflow Overview / कार्य प्रवाह सिंहावलोकन

## 2.1 Previous vs New Workflow / पूर्व र नयाँ कार्यप्रवाह

### Previous (v1.6.0): 5-Step Process / 5-चरण प्रक्रिया

```
[Step 1] → [Step 2] → [Step 3] → [Step 4] → [Step 5]
  ↓          ↓           ↓          ↓          ↓
GPS      Boundary    Blocks     Sub-areas   Review
Points   (Map)      (Map)      (Map)      (Map)
```

**Issues:**
- 5 different pages/sections
- Multiple map instances (slow loading)
- 8+ buttons to navigate
- Complex step-by-step process
- समस्याहरू:
- 5 वटा फरक पृष्ठहरू/खण्डहरू
- धेरै नक्शा उदाहरणहरू (ढिलो लोडिंग)
- ८+ वटा बटनहरू नेभिगेसनको लागि
- जटिल चरण-दर-चरण प्रक्रिया

### New (v1.7.0): 2-Step Process / 2-चरण प्रक्रिया

```
[Page 1: Create & Configure]     [Page 2: Review & Save]
┌────────────────────────┐       ┌────────────────────────┐
│  MAP (70%)             │       │  MAP (60%)             │
│  + Sidebar (30%)       │  →   │  + Summary Panel       │
│    - Islands           │       │    - Blocks            │
│    - Blocks            │       │    - Sub-areas        │
│    - Sub-areas         │       │    - Total areas       │
│    - Save buttons      │       │    - Save/Back        │
└────────────────────────┘       └────────────────────────┘
```

**Benefits:**
- 2 main sections (Create → Review)
- Single map instance
- 4-5 buttons total
- Inline editing
- Faster workflow
- लाभहरू:
- २ मुख्य खण्डहरू (सिर्जना → समीक्षा)
- एकल नक्शा उदाहरण
- कुल ४-५ वटा बटनहरू
- इनलाइन सम्पादन
- छिटो कार्यप्रवाह

## 2.2 Visual Comparison / दृश्य तुलना

### Page 1 Layout: Draw & Configure / पृष्ठ 1: कोरियौं र कन्फिगर गर्नुहोस्

```
┌─────────────────────────────────────────────────────────────┐
│ Header: "Create Forest Map: [Forest Name]"        [Cancel] │
├─────────────────────────────────────┬───────────────────────┤
│                                     │ 📍 GPS Points         │
│                                     │ ┌───────────────────┐ │
│                                     │ │ (Collapsible)    │ │
│           🗺️ MAP                    │ │ GPS coordinates   │ │
│        (70% width)                  │ │ will appear here  │ │
│                                     │ └───────────────────┘ │
│   • Draw polygons here               ├───────────────────────┤
│   • Multiple islands supported        │ 🏝️ Islands (3)       │
│   • Click to add vertices           │ ┌───────────────────┐ │
│   • Double-click to complete        │ │ Island 1 [3.7 ha]│ │
│                                     │ │ Island 2 [7.2 ha]│ │
│                                     │ │ Island 3 [6.6 ha]│ │
│                                     │ └───────────────────┘ │
│                                     │ [+ Add Island]        │
│                                     ├───────────────────────┤
│                                     │ 📦 Blocks (3)         │
│                                     │ ┌───────────────────┐ │
│                                     │ │ Block 1  [Edit]  │ │
│                                     │ │ Block 2  [Edit]  │ │
│                                     │ │ Block 3  [Edit]  │ │
│                                     │ └───────────────────┘ │
│                                     │ [Auto: 1 block per  │
│                                     │  island]              │
│                                     ├───────────────────────┤
│                                     │ 🗺️ Sub-areas (0)      │
│                                     │ [Add Protected Zone]   │
│                                     │ [Add Plantation]      │
│                                     ├───────────────────────┤
│                                     │ [Save Draft] [Save →] │
└─────────────────────────────────────┴───────────────────────┘
```

### Page 2 Layout: Review & Save / पृष्ठ 2: समीक्षा र बचत गर्नुहोस्

```
┌─────────────────────────────────────────────────────────────┐
│ Header: "Review: [Forest Name]"                    [Back] │
├─────────────────────────────────────┬───────────────────────┤
│                                     │ 📋 Summary            │
│                                     ├───────────────────────┤
│           🗺️ MAP                    │ 🌲 Forest Info        │
│        (60% width)                  │ Name: Rakuri Digitize │
│                                     │ Total Area: 53.2 ha   │
│   • Shows all polygons              ├───────────────────────┤
│   • Shows blocks (blue)            │ 📦 Blocks (3)         │
│   • Shows sub-areas (colors)       │ ┌───────────────────┐ │
│                                     │ │ Block 1:  3.7 ha │ │
│                                     │ │ Block 2:  7.2 ha │ │
│                                     │ │ Block 3:  6.6 ha │ │
│                                     │ │ + 7 more...      │ │
│                                     │ └───────────────────┘ │
│                                     │ [Edit Blocks]          │
│                                     ├───────────────────────┤
│                                     │ 🗺️ Sub-areas (2)      │
│                                     │ ┌───────────────────┐ │
│                                     │ │ Protected: 2.1 ha│ │
│                                     │ │ Plantation: 1.5ha│ │
│                                     │ └───────────────────┘ │
│                                     ├───────────────────────┤
│                                     │ [Back] [Save Forest]  │
└─────────────────────────────────────┴───────────────────────┘
```

---

# 3. Step-by-Step Guide / चरण-दर-चरण मार्गदर्शिका

## Phase 1: Getting Started / चरण १: सुरु गर्नुहोस्

### Step 1.1: Login to the System / चरण १.१: प्रणालीमा लगइन गर्नुहोस्

**English:**
1. Open your web browser (Chrome recommended)
2. Go to: http://localhost:3001
3. Enter your email and password
4. Click "Login" button
5. You will be redirected to the dashboard

**नेपाली:**
1. आफ्नो वेब ब्राउजर खोल्नुहोस् (Chrome सिफारिस गरिन्छ)
2. जानुहोस्: http://localhost:3001
3. आफ्नो इमेल र पासवर्ड प्रविष्टि गर्नुहोस्
4. "Login" बटनमा क्लिक गर्नुहोस्
5. तपाईं ड्यासबोर्डमा पुन: निर्देशित हुनुहुनेछ

### Step 1.2: Start New Map Creation / चरण १.२: नयाँ नक्शा सिर्जना सुरु गर्नुहोस्

**English:**
1. From the dashboard, click "Upload New CF Boundary"
2. Or click "Create New Map" button
3. Enter your forest name in Nepali or English
4. Click "Start Creating" to begin

**नेपाली:**
1. ड्यासबोर्डबाट, "Upload New CF Boundary" मा क्लिक गर्नुहोस्
2. वा "Create New Map" बटनमा क्लिक गर्नुहोस्
3. तपाईंको वनको नाम नेपाली वा अंग्रेजीमा प्रविष्टि गर्नुहोस्
4. सुरु गर्न "Start Creating" मा क्लिक गर्नुहोस्

---

## Phase 2: Drawing the Boundary / चरण २: सीमाना कोर्नुहोस्

### Step 2.1: Understanding the Interface / चरण २.१: इन्टरफेस बुझ्नुहोस्

**English:**
The main screen has two areas:
- **Map Area (70%)**: Where you draw polygons
- **Sidebar (30%)**: Where you manage islands, blocks, and sub-areas

**नेपाली:**
मुख्य स्क्रिनमा दुईवटा क्षेत्रहरू छन्:
- **नक्शा क्षेत्र (70%)**: जहाँ तपाईं बहुभुजहरू कोर्नुहुन्छ
- **साइडबार (30%)**: जहाँ तपाईं टापुहरू, ब्लकहरू, र उप-क्षेत्रहरू प्रबन्ध गर्नुहुन्छ

### Step 2.2: Add Your First Island / चरण २.२: तपाईंको पहिलो टापु थप्नुहोस्

**English:**
1. Click the **"+ Add Island"** button in the sidebar
   - This enables the polygon drawing tool
2. Click the **polygon icon** in the map toolbar (appears automatically)
3. Click on the map to add vertices (corner points)
4. Double-click to complete the polygon
5. The island will appear in the sidebar list with its area

**नेपाली:**
1. साइडबारमा **"+ Add Island"** बटनमा क्लिक गर्नुहोस्
   - यसले बहुभुज आरेखन उपकरण सक्षम गर्छ
2. नक्शा टूलबारमा **बहुभुज आइकन** मा क्लिक गर्नुहोस् (स्वचालित रूपमा देखा पर्छ)
3. शीर्षकहरू (कोण बिंदुहरू) थप्न नक्शामा क्लिक गर्नुहोस्
4. बहुभुज पूरा गर्न डबल-क्लिक गर्नुहोस्
5. टापु साइडबार सूचीमा यसको क्षेत्रफलसँग देखा पर्नेछ

### Step 2.3: Add Multiple Islands / चरण २.३: धेरै टापुहरू थप्नुहोस्

**English:**
If your forest has multiple separate areas (islands):

1. After completing the first island, click **"+ Add Island"** again
2. The polygon tool will be enabled automatically
3. Draw the second island in a different location
4. Repeat for additional islands
5. Each island becomes a separate block automatically

**नेपाली:**
यदि तपाईंको वनमा धेरै अलग-अलग क्षेत्रहरू (टापुहरू) छन्:

1. पहिलो टापु पूरा गरेपछि, फेरि **"+ Add Island"** मा क्लिक गर्नुहोस्
2. बहुभुज उपकरण स्वचालित रूपमा सक्षम हुनेछ
3. फरक स्थानमा दोस्रो टापु कोर्नुहोस्
4. अतिरिक्त टापुहरूको लागि दोहोर्याउनुहोस्
5. प्रत्येक टापु स्वचालित रूपमा छुट्टै ब्लक बन्छ

### Step 2.4: Drawing Tips / चरण २.४: कोर्नका सुझावहरू

**English:**
- **Click precisely**: Each click adds a vertex
- **Use satellite imagery**: Toggle to satellite view for accuracy
- **Zoom in/out**: Use mouse wheel or +/- buttons
- **Pan the map**: Click and drag to move around
- **Edit existing polygons**: Use the edit tool to modify vertices

**नेपाली:**
- **सही क्लिक गर्नुहोस्**: प्रत्येक क्लिकले शीर्षक थप्छ
- **उपग्रह छवि प्रयोग गर्नुहोस्**: सहीताको लागि उपग्रह दृश्यमा टगल गर्नुहोस्
- **जुम इन/आउट गर्नुहोस्**: माउस ह्वील वा +/- बटनहरू प्रयोग गर्नुहोस्
- **नक्शा प्यान गर्नुहोस्**: घुमाउन क्लिक र ड्र्याग गर्नुहोस्
- **अवस्थित बहुभुजहरू सम्पादन गर्नुहोस्**: शीर्षकहरू परिवर्तन गर्न सम्पादन उपकरण प्रयोग गर्नुहोस्

---

## Phase 3: Managing Blocks / चरण ३: ब्लकहरू प्रबन्ध गर्नुहोस्

### Step 3.1: Understanding Auto-Block Creation / चरण ३.१: स्वचालित-ब्लक सिर्जना बुझ्नुहोस्

**English:**
- By default, each island automatically becomes one block
- Block 1 = Island 1, Block 2 = Island 2, etc.
- You can rename blocks or split them further

**नेपाली:**
- पूर्वनिर्धारित रूपमा, प्रत्येक टापु स्वचालित रूपमा एउटा ब्लक बन्छ
- ब्लक 1 = टापु 1, ब्लक 2 = टापु 2, आदि।
- तपाईं ब्लकहरूको नाम परिवर्तन गर्न सक्नुहुन्छ वा तिनीहरूलाई थप विभाजन गर्न सक्नुहुन्छ

### Step 3.2: Rename a Block / चरण ३.२: ब्लकको नाम परिवर्तन गर्नुहोस्

**English:**
1. Find the block in the sidebar under "Blocks (X)"
2. Click on the block name field
3. Type the new name (e.g., "North Section", "Upper Block")
4. Press Enter or click outside to save

**नेपाली:**
1. "Blocks (X)" अन्तर्गत साइडबारमा ब्लक फेला पार्नुहोस्
2. ब्लक नाम फाइल्डमा क्लिक गर्नुहोस्
3. नयाँ नाम टाइप गर्नुहोस् (जस्तै, "उत्तर खण्ड", "माथिल्लो ब्लक")
4. बचत गर्न Enter थिच्नुहोस् वा बाहिर क्लिक गर्नुहोस्

### Step 3.3: Split a Block (Advanced) / चरण ३.३: ब्लक विभाजन गर्नुहोस् (उन्नत)

**English:**
If you need to divide one block into multiple sections:

1. Click on the block name in the sidebar
2. Select "Split Block" from the dropdown
3. Use the line tool to draw division lines
4. Click "Apply" to create new blocks
5. Rename the new blocks as needed

**नेपाली:**
यदि तपाईंले एउटा ब्लकलाई धेरै खण्डहरूमा विभाजन गर्न आवश्यक छ:

1. साइडबारमा ब्लक नाममा क्लिक गर्नुहोस्
2. ड्रपडाउनबाट "Split Block" चयन गर्नुहोस्
3. नयाँ ब्लकहरू सिर्जना गर्न रेखा उपकरण प्रयोग गर्नुहोस्
4. नयाँ ब्लकहरू सिर्जना गर्न "Apply" मा क्लिक गर्नुहोस्
5. आवश्यकताअनुसार नयाँ ब्लकहरूको नाम परिवर्तन गर्नुहोस्

---

## Phase 4: Adding Sub-areas / चरण ४: उप-क्षेत्रहरू थप्नुहोस्

### Step 4.1: What are Sub-areas? / चरण ४.१: उप-क्षेत्रहरू के हुन्?

**English:**
Sub-areas are special zones within your forest that have different management purposes:
- **Protected Zone**: Areas with special conservation status
- **Plantation Area**: Areas designated for tree planting
- **Pro-Poor Income**: Areas for community income generation
- **Religious Area**: Sacred or religious sites
- **Bio-diversity Rich**: High biodiversity zones
- **Tourist Attraction**: Areas for tourism activities
- **Private Land**: Areas excluded from forest calculations

**नेपाली:**
उप-क्षेत्रहरू तपाईंको वनभित्रका विशेष क्षेत्रहरू हुन् जसका विभिन्न प्रबन्ध उद्देश्यहरू छन्:
- **संरक्षित क्षेत्र**: विशेष संरक्षण स्थिति भएका क्षेत्रहरू
- **रोपण क्षेत्र**: वृक्ष रोपणको लागि निर्दिष्ट क्षेत्रहरू
- **गरिब-उन्मुख आय**: सामुदायिक आय सिर्जनाको लागि क्षेत्रहरू
- **धार्मिक क्षेत्र**: पवित्र वा धार्मिक स्थलहरू
- **जैविक विविधता सम्पन्न**: उच्च जैविक विविधता भएका क्षेत्रहरू
- **पर्यटक आकर्षण**: पर्यटन गतिविधिहरूको लागि क्षेत्रहरू
- **निजी जमिन**: वन गणनाबाट बाहिर गरिएका क्षेत्रहरू

### Step 4.2: Add a Sub-area / चरण ४.२: उप-क्षेत्र थप्नुहोस्

**English:**
1. Scroll to the "Sub-areas" section in the sidebar
2. Click on the category you want (e.g., "Protected Zone")
3. The polygon tool will be enabled
4. Draw the sub-area inside your forest boundary
5. The sub-area will appear in the list with its details

**नेपाली:**
1. साइडबारमा "Sub-areas" खण्डमा स्क्रोल गर्नुहोस्
2. तपाईंले चाहानुभएको श्रेणीमा क्लिक गर्नुहोस् (जस्तै, "संरक्षित क्षेत्र")
3. बहुभुज उपकरण सक्षम हुनेछ
4. तपाईंको वन सीमाना भित्र उप-क्षेत्र कोर्नुहोस्
5. उप-क्षेत्र यसको विवरणहरूसहित सूचीमा देखा पर्नेछ

### Step 4.3: Add Private Land (Excluded Areas) / चरण ४.३: निजी जमिन थप्नुहोस् (बाहिर गरिएका क्षेत्रहरू)

**English:**
If there are private lands within your forest boundary:
1. Click "Private Land (Excluded)" category
2. Draw the private land area
3. This area will be excluded from forest calculations
4. It will be shown in red in the summary

**नेपाली:**
यदि तपाईंको वन सीमाना भित्र निजी जमिनहरू छन्:
1. "निजी जमिन (बाहिर गरिएको)" श्रेणीमा क्लिक गर्नुहोस्
2. निजी जमिन क्षेत्र कोर्नुहोस्
3. यो क्षेत्र वन गणनाबाट बाहिर गरिनेछ
4. यो समीक्षामा रातो रंगमा देखाइनेछ

---

## Phase 5: Saving Your Work / चरण ५: तपाईंको काम बचत गर्नुहोस्

### Step 5.1: Save as Draft / चरण ५.१: ड्राफ्टको रूपमा बचत गर्नुहोस्

**English:**
If you need to stop and continue later:
1. Click **"Save Draft"** button at the bottom of the sidebar
2. Wait for the success message
3. You can close the browser
4. When you return, click **"Resume Draft"** from your list

**नेपाली:**
यदि तपाईंले रोक्न र पछि जारी राख्न आवश्यक छ:
1. साइडबारको तल **"Save Draft"** बटनमा क्लिक गर्नुहोस्
2. सफलता सन्देशको लागि पर्खनुहोस्
3. तपाईं ब्राउजर बन्द गर्न सक्नुहुन्छ
4. फर्कदा, तपाईंको सूचीबाट **"Resume Draft"** मा क्लिक गर्नुहोस्

### Step 5.2: Review and Save / चरण ५.२: समीक्षा र बचत गर्नुहोस्

**English:**
When ready to complete:
1. Click **"Save →"** or **"Next"** button
2. Review page will show:
   - All blocks with areas
   - All sub-areas with categories
   - Map visualization
3. Make any final edits if needed
4. Click **"Save Forest"** to complete

**नेपाली:**
पूरा गर्न तयार हुँदा:
1. **"Save →"** वा **"Next"** बटनमा क्लिक गर्नुहोस्
2. समीक्षा पृष्ठले देखाउनेछ:
   - सबै ब्लकहरू क्षेत्रफलसहित
   - सबै उप-क्षेत्रहरू श्रेणीहरूसहित
   - नक्शा दृश्य
3. आवश्यक भएमा कुनै अन्तिम सम्पादनहरू गर्नुहोस्
4. पूरा गर्न **"Save Forest"** मा क्लिक गर्नुहोस्

---

## Phase 6: After Saving / चरण ६: बचत पछि

### Step 6.1: What Happens Next? / चरण ६.१: त्यसपछि के हुन्छ?

**English:**
After saving:
1. You'll be redirected to the Analysis page
2. You can run forest analysis on your boundary
3. Species analysis will be performed
4. Sampling designs can be created

**नेपाली:**
बचत पछि:
1. तपाईं विश्लेषण पृष्ठमा पुन: निर्देशित हुनुहुनेछ
2. तपाईं आफ्नो सीमानामा वन विश्लेषण चलाउन सक्नुहुन्छ
3. प्रजाति विश्लेषण गरिनेछ
4. नमूना डिजाइनहरू सिर्जना गर्न सकिन्छ

---

# 4. Best Practices / उत्तम अभ्यासहरू

## 4.1 Before You Start / सुरु गर्नु अघि

| Practice / अभ्यास | Reason / कारण |
|-------------------|--------------|
| Have GPS coordinates ready | Accurate boundary positioning |
| Use satellite imagery | Better visualization of boundaries |
| Know your forest area | Helps identify islands and blocks |
| Gather community input | Ensures all areas are covered |
| GPS निर्देशांक तयार राख्नुहोस् | सही सीमाना स्थिति |
| उपग्रह छवि प्रयोग गर्नुहोस् | सीमानाहरूको राम्रो दृश्य |
| आफ्नो वन क्षेत्र थाहा पाउनुहोस् | टापुहरू र ब्लकहरू पहिचान गर्न मद्दत गर्छ |
| समुदायको इनपुट संकलन गर्नुहोस् | सबै क्षेत्रहरू समेटिएको सुनिश्चित गर्छ |

## 4.2 While Drawing / कोर्दै गर्दा

| Practice / अभ्यास | Reason / कारण |
|-------------------|--------------|
| Zoom in for precision | Accurate vertex placement |
| Cross-check with GPS | Ensure boundary matches reality |
| Save frequently | Prevent work loss |
| Name blocks clearly | Easier management later |
| Accuracy को लागि जुम इन गर्नुहोस् | सही शीर्षक राख्ने |
| GPS सँग क्रस-चेक गर्नुहोस् | सीमाना वास्तविकतासँग मेल खान्छ भनेर सुनिश्चित गर्छ |
| बारम्बार बचत गर्नुहोस् | काम गुम्नबाट रोक्छ |
| ब्लकहरूलाई स्पष्ट नाम दिनुहोस् | पछि प्रबन्ध गर्न सजिलो |

## 4.3 Common Mistakes to Avoid / रोक्नुपर्ने सामान्य गल्तीहरू

| Mistake / गल्ती | Solution / समाधान |
|-----------------|------------------|
| Drawing outside boundary | Always stay within forest perimeter |
| Overlapping polygons | Use edit tool to fix overlaps |
| Forgetting to save | Click "Save Draft" regularly |
| Skipping island numbers | Label islands clearly |
| सीमाना बाहिर कोर्नु | सधैं वन परिधिभित्र रहनुहोस् |
| बहुभुजहरू ओभरल्याप गर्नु | सुधार गर्न सम्पादन उपकरण प्रयोग गर्नुहोस् |
| बचत बिर्सनु | नियमित रूपमा "Save Draft" मा क्लिक गर्नुहोस् |
| टापु नम्बरहरू बिर्सनु | टापुहरूलाई स्पष्ट रूपमा लेबल गर्नुहोस् |

---

# 5. Troubleshooting / समस्या समाधान

## 5.1 Common Issues / सामान्य समस्याहरू

### Issue: Cannot draw polygon / समस्या: बहुभुज कोर्न सकिएन

**English:**
- Make sure you clicked "+ Add Island" first
- Check if polygon tool is enabled (icon should be highlighted)
- Try refreshing the page

**नेपाली:**
- पहिले "+ Add Island" मा क्लिक गर्नुभएको सुनिश्चित गर्नुहोस्
- बहुभुज उपकरण सक्षम छ कि छैन जाँच्नुहोस् (आइकन हाइलाइट हुनुपर्छ)
- पृष्ठ रिफ्रेस गर्ने प्रयास गर्नुहोस्

### Issue: Map not loading / समस्या: नक्शा लोड हुँदैन

**English:**
- Check your internet connection
- Try a different browser (Chrome recommended)
- Clear browser cache
- Restart the application

**नेपाली:**
- आफ्नो इन्टरनेट जडान जाँच्नुहोस्
- फरक ब्राउजर प्रयोग गर्ने प्रयास गर्नुहोस् (Chrome सिफारिस)
- ब्राउजर क्यास खाली गर्नुहोस्
- एप्लिकेसन पुन: सुरु गर्नुहोस्

### Issue: Draft not resuming / समस्या: ड्राफ्ट फर्कदैन

**English:**
- Make sure you're logged in with the same account
- Check if the draft still exists in "My Uploads"
- Try saving a new draft if old one is corrupted

**नेपाली:**
- तपाईं उही खाताबाट लगइन गर्नुभएको सुनिश्चित गर्नुहोस्
- "My Uploads" मा ड्राफ्ट अझै अवस्थित छ कि छैन जाँच्नुहोस्
- पुरानो दूषित भएमा नयाँ ड्राफ्ट बचत गर्ने प्रयास गर्नुहोस्

### Issue: Save fails / समस्या: बचत असफल

**English:**
- Check browser console for errors (F12)
- Try refreshing and saving again
- Ensure you're logged in
- Contact support if problem persists

**नेपाली:**
- त्रुटिहरूको लागि ब्राउजर कन्सोल जाँच्नुहोस् (F12)
- रिफ्रेस गरेर फेरि बचत गर्ने प्रयास गर्नुहोस्
- तपाईं लगइन गर्नुभएको सुनिश्चित गर्नुहोस्
- समस्या जारी रहेमा समर्थनसँग सम्पर्क गर्नुहोस्

## 5.2 Keyboard Shortcuts / कीबोर्ड सर्टकटहरू

| Shortcut / सर्टकट | Action / कार्य |
|-------------------|----------------|
| Ctrl + S | Save Draft |
| Ctrl + Z | Undo |
| Ctrl + Y | Redo |
| Delete | Remove selected polygon |
| Escape | Cancel current drawing |

---

# 6. Quick Reference Card / द्रुत संदर्भ कार्ड

## Drawing Workflow / कोर्ने कार्यप्रवाह

```
┌─────────────────────────────────────────────────────────────┐
│                    QUICK REFERENCE                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Click "+ Add Island"                                    │
│ 2. Click polygon tool in toolbar                           │
│ 3. Click to add vertices                                   │
│ 4. Double-click to finish                                  │
│ 5. Repeat for more islands                                  │
│ 6. Rename blocks (if needed)                               │
│ 7. Add sub-areas (if needed)                               │
│ 8. Click "Save →"                                          │
│ 9. Review and "Save Forest"                                │
└─────────────────────────────────────────────────────────────┘
```

## Sidebar Sections / साइडबार खण्डहरू

```
┌────────────────────────────────────────┐
│ 📍 GPS Points (Optional)                │
│    - Enter coordinates manually        │
├────────────────────────────────────────┤
│ 🏝️ Islands (Auto from drawings)        │
│    - List of all islands              │
│    - Shows area for each              │
│    - "+ Add Island" button             │
├────────────────────────────────────────┤
│ 📦 Blocks (1 per island by default)   │
│    - Editable names                   │
│    - Area displayed                   │
│    - Can split into more blocks       │
├────────────────────────────────────────┤
│ 🗺️️ Sub-areas (Optional)               │
│    - Category buttons                 │
│    - Different colors                 │
│    - Can exclude private land         │
├────────────────────────────────────────┤
│ 💾 Save Options                       │
│    - Save Draft (continue later)      │
│    - Save → (review & complete)       │
└────────────────────────────────────────┘
```

---

# Appendix A: Glossary / परिशिष्ट: शब्दावली

| Term / शब्द | Definition / परिभाषा |
|-------------|---------------------|
| Island / टापु | A separate polygon representing part of the forest |
| Block / ब्लक | A management unit within the forest |
| Sub-area / उप-क्षेत्र | A special zone with specific management purpose |
| Boundary / सीमाना | The outer edge of the forest area |
| Vertex / शीर्षक | A corner point of a polygon |
| Draft / ड्राफ्ट | Saved work-in-progress |

---

# Appendix B: Contact Information / परिशिष्ट: सम्पर्क जानकारी

For technical support:
- Email: support@cfms.nepal
- Phone: +977-1-XXXXXXX
- Website: www.cfms.nepal

---

**Document Created**: March 2026
**Version**: 1.0
**For**: CFMS v1.7.0 Streamlined Workflow
