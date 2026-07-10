# 📊 PDF REPORT GENERATION - COMPLETE GUIDE

## ✅ WHAT'S FIXED

- **PDF Generation**: Now generates PDFs reliably with reportlab
- **Auto Folder Creation**: Creates `reports/` folder automatically
- **File Naming**: Saves as `reports/report_YYYYMMDD_HHMMSS.pdf`
- **Debug Logging**: Full console output showing every step
- **Error Handling**: Try-except with detailed error messages
- **Evidence Inclusion**: Adds alert images with captions
- **Summary Data**: Includes total students, alerts, behavior types

---

## 🎯 QUICK START

### Option 1: Direct Function Call (Recommended)

```python
from generate_pdf_report import generate_report

# Your alert data
alerts = [
    {
        "id": 1,
        "type": "Using Mobile",
        "time": "10:05:12",
        "image_path": "evidence/1.jpg"  # Optional
    },
    {
        "id": 2,
        "type": "Looking Around",
        "time": "10:10:30",
        "image_path": "evidence/2.jpg"
    }
]

# Summary data
summary = {
    "total_students": 30,
    "active_ids": 28,
    "total_alerts": 2,
    "normal_students": 26
}

# Generate report
pdf_path = generate_report(alerts, summary)

# ✅ Output: reports/report_20260419_143522.pdf
print(f"Report saved: {pdf_path}")
```

### Option 2: API Endpoint

When API server is running, make a POST request:

```bash
curl -X POST http://localhost:5000/api/reports/generate
```

Response:
```json
{
  "success": true,
  "message": "Report generated successfully",
  "report_path": "reports/report_20260419_143522.pdf",
  "file_size": 4263,
  "total_alerts": 4,
  "total_students": 30,
  "timestamp": "2026-04-19T15:35:22"
}
```

### Option 3: Command Line Test

```bash
cd "d:\mini project\mini project"
python generate_pdf_report.py
```

Output:
```
############################################################
# 🧪 TESTING PDF REPORT GENERATION
############################################################

============================================================
📄 GENERATING PDF REPORT
============================================================
📁 Checking reports folder...
   ✅ Folder exists: reports/

📝 Generating filename...
   📌 Filename: report_20260419_151622.pdf
   📌 Full path: reports\report_20260419_151622.pdf

📋 Creating PDF document...
   ✅ PDF document object created

🎨 Setting up styles...
   ✅ Styles configured

🏗️  Building report elements...
   • Adding header...
   • Adding summary section...
   • Adding alerts table...
   • Adding evidence section...
   • Adding footer...
   ✅ All elements added to story

🔨 Building PDF document...
   ✅ PDF built successfully

✅ VERIFYING REPORT
============================================================
✅ Report generated successfully!
📁 Location: D:\mini project\mini project\reports\report_20260419_151622.pdf    
💾 Size: 4,263 bytes (4.16 KB)
⏰ Created: 2026-04-19 15:16:22
📊 Alerts: 4
📈 Summary: 30 students, 4 alerts
============================================================

✅ TEST PASSED - Report generated: reports\report_20260419_151622.pdf
```

---

## 📋 DATA FORMAT

### Alert Object
```python
alert = {
    "id": 1,                          # Student/Track ID (int)
    "type": "Using Mobile",           # Behavior type (str)
    "time": "10:05:12",               # Time HH:MM:SS (str)
    "image_path": "evidence/1.jpg"    # Optional: path to evidence image
}
```

**Alert Types Supported:**
- `Using Mobile` → 🔴 ALERT
- `Looking to Copy` → 🔴 ALERT
- `Looking Around` → 🟠 WARNING
- `Leaning` → 🟠 WARNING
- `Sharing Answers` → 🔴 ALERT
- Any custom type → ⚪ INFO

### Summary Object
```python
summary = {
    "total_students": 30,      # Total students monitored
    "active_ids": 28,          # Students detected in frame
    "total_alerts": 2,         # Total alerts triggered
    "normal_students": 26      # Students with normal behavior
}
```

---

## 📁 FILE STRUCTURE

```
mini project/
├── generate_pdf_report.py      ← New report generator
├── api_server.py               ← Updated with report integration
├── reports/                    ← Output folder (auto-created)
│   ├── report_20260419_151622.pdf
│   ├── report_20260419_152245.pdf
│   └── ...more reports
├── evidence/                   ← Alert images
│   ├── ID1_151622.jpg
│   ├── ID2_151630.jpg
│   └── ...more images
└── logs/
    └── alerts_log.json
```

---

## 🔍 DEBUG OUTPUT EXPLAINED

```
============================================================
📄 GENERATING PDF REPORT
============================================================
```
**Starting report generation process**

```
📁 Checking reports folder...
   ⚠️  Folder '{reports}' not found, creating...
   ✅ Folder created: reports/
```
**Creates folder if it doesn't exist**

```
📝 Generating filename...
   📌 Filename: report_20260419_151622.pdf
   📌 Full path: reports\report_20260419_151622.pdf
```
**Generates timestamp-based filename**

```
📋 Creating PDF document...
   ✅ PDF document object created
```
**Initializes ReportLab PDF object**

```
🎨 Setting up styles...
   ✅ Styles configured
```
**Configures text styles, colors, formatting**

```
🏗️  Building report elements...
   • Adding header...
   • Adding summary section...
   • Adding alerts table...
   • Adding evidence section...
   • Adding footer...
   ✅ All elements added to story
```
**Builds all report sections**

```
🔨 Building PDF document...
   ✅ PDF built successfully
```
**Writes PDF to disk**

```
✅ VERIFYING REPORT
============================================================
✅ Report generated successfully!
📁 Location: D:\mini project\mini project\reports\report_20260419_151622.pdf    
💾 Size: 4,263 bytes (4.16 KB)
⏰ Created: 2026-04-19 15:16:22
📊 Alerts: 4
📈 Summary: 30 students, 4 alerts
============================================================
```
**Verifies file exists and shows statistics**

---

## ❌ ERROR HANDLING

If something goes wrong, you'll see:

```
❌ ERROR DURING REPORT GENERATION
============================================================
Exception: FileNotFoundError
Message: [Errno 2] No such file or directory: 'evidence/1.jpg'
============================================================
```

**Common Issues & Solutions:**

| Problem | Solution |
|---------|----------|
| `reports` folder doesn't exist | ✅ Auto-created by function |
| Image file not found | ✅ Function skips missing images |
| No alerts to display | ✅ Shows "No suspicious activity" message |
| PDF generation fails | ✅ Returns None and prints error |
| Permission denied | ✅ Check file permissions on `reports/` folder |

---

## 🔗 INTEGRATION POINTS

### In API Server (When Surveillance Ends)

```python
# api_server.py - surveillance_loop() finally block
pdf_path = generate_report(alerts_list, summary_data)
if pdf_path:
    print(f"✅ PDF Report saved: {pdf_path}")
else:
    print("⚠️  PDF generation encountered an issue")
```

### In Report System (Standalone)

```python
from generate_pdf_report import generate_report

# Called independently when you need a report
pdf_path = generate_report(alerts, summary)
```

### Via API Endpoint

```python
# POST /api/reports/generate
# Returns JSON with report details
```

---

## 📈 PDF REPORT CONTENTS

### 1️⃣ HEADER
- Title: "🎓 AI EXAM SURVEILLANCE REPORT"
- Generated date/time
- Professional formatting

### 2️⃣ MONITORING SUMMARY
- Total Students
- Active IDs detected
- Total Alerts
- Normal Students

### 3️⃣ ALERT DETAILS TABLE
| ID | Behavior | Time | Status |
|----|----------|------|--------|
| 1 | Using Mobile | 10:05:12 | 🔴 ALERT |
| 2 | Looking Around | 10:10:30 | 🟠 WARNING |

### 4️⃣ EVIDENCE SECTION
- Alert-based images with captions
- Student ID, Behavior, Time
- Up to 10 most recent alerts
- Page breaks for readability

### 5️⃣ FOOTER
- Auto-generated message

---

## ✨ FEATURES

✅ **Reliable**: Uses reportlab, battle-tested PDF library  
✅ **Auto Folder**: Creates `reports/` if missing  
✅ **Timestamp**: Unique filename every time  
✅ **Full Logging**: See every step in console  
✅ **Error Safe**: Try-except with good error messages  
✅ **Evidence**: Includes alert images in PDF  
✅ **Summary**: Complete monitoring statistics  
✅ **Professional**: Clean, formatted PDF output  

---

## 🚀 NEXT STEPS

1. ✅ Test the function: `python generate_pdf_report.py`
2. ✅ Check reports folder: `reports/report_*.pdf`
3. ✅ Use in API: `POST /api/reports/generate`
4. ✅ Integrate in monitoring: Called automatically when surveillance ends
5. ✅ Email reports: Configure email in `report_integration.py`

---

## 📞 TROUBLESHOOTING

**Q: PDF not being created?**  
A: Check console for error messages, ensure `reportlab` is installed

**Q: Folder not created?**  
A: Function auto-creates it, check file permissions

**Q: Images not showing in PDF?**  
A: Verify image paths are correct, images exist

**Q: File size very large?**  
A: Normal for many high-res images, consider resizing

**Q: Want to customize?**  
A: Edit `generate_pdf_report.py` - code is well-commented

---

## 📝 DEPENDENCIES

- `reportlab==4.0.7` ✅ Already installed
- `python>=3.8`
- `os`, `datetime` (standard library)

---

**Created: 2026-04-19**  
**Status: ✅ FULLY WORKING**  
**Test Result: ✅ PASSED**
