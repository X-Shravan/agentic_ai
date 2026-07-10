# 📄 Student Detection PDF Reports - Complete Guide

## Overview

Your system can now generate **individual PDF reports for each student** containing:
- 📅 Detailed detection timeline
- 📊 Behavior statistics and breakdown
- ⚠️ Risk assessment score (0-100)
- 📸 Evidence images with captions
- 🎯 Summary statistics

---

## Files Created

### 1. **student_detection_pdf_generator.py**
Core PDF generation engine:
- `StudentDetectionReportGenerator` class
- Handles individual student report generation
- Generates professional, formatted PDFs
- Supports batch generation

### 2. **student_report_integration.py**
Integration layer for API server:
- `StudentReportManager` class
- Records detections and evidence during surveillance
- Generates all reports at end of session
- Creates HTML index page for easy access

---

## How to Use

### Option 1: Automatic (Integrated with API Server)

**Step 1: Initialize in api_server.py**
```python
# At startup (in surveillance_loop function)
from student_report_integration import initialize_student_reports, record_student_detection

# Initialize
student_reports = initialize_student_reports()

# During surveillance loop (when creating alert)
record_student_detection(student_id, {
    "timestamp": "10:05:30",
    "behavior_type": "Using Mobile 📱",
    "confidence": 0.92,
    "label": "Alert 🚨",
    "situation": "using_mobile 📱 🚨"
})

# At end of surveillance (in surveillance_loop finally block)
from student_report_integration import generate_student_reports
generate_student_reports()  # Generates all PDFs
```

### Option 2: Manual PDF Generation

```python
from student_detection_pdf_generator import StudentDetectionReportGenerator

# Initialize generator
generator = StudentDetectionReportGenerator()

# Generate report for one student
detections = [
    {
        "timestamp": "10:05:30",
        "behavior_type": "Using Mobile 📱",
        "confidence": 0.92,
        "label": "Alert 🚨",
        "situation": "using_mobile 📱 🚨"
    }
]

evidence = ["evidence/student_1_photo.jpg"]

pdf_path = generator.generate_student_report(
    student_id=1,
    detections_log=detections,
    evidence_images=evidence
)

print(f"PDF saved to: {pdf_path}")
```

---

## PDF Report Contents

### 📋 Header Section
```
EXAM SURVEILLANCE REPORT
Student ID: 1
Report Generated: April 19, 2026 at 10:30:45
```

### 📊 Summary Statistics
| Metric | Value |
|--------|-------|
| Total Events Detected | 5 |
| Alert-Level Events | 2 |
| Mobile Phone Detections | 1 |
| Most Common Behavior | Looking Around |

### 📅 Detection Timeline
```
Time    | Behavior Type       | Confidence | Status | Details
--------|-------------------|------------|--------|------------------
10:05   | Using Mobile      | 92%        | 🚨     | using_mobile 🚨
10:10   | Looking Around    | 78%        | ⚠️     | looking_around 👀
10:15   | Looking to Copy   | 85%        | ⚠️     | looking_to_copy 📄
```

### 📊 Behavior Breakdown
```
Behavior Type           Count   Percentage
Looking Around          3       60%
Using Mobile           1       20%
Looking to Copy        1       20%
```

### ⚠️ Risk Assessment
```
Risk Factor              Count   Impact
Alert-Level Events       2       High
Mobile Phone Detection   1       High
Suspicious Events        2       Medium

🔴 HIGH RISK - Score: 65/100
```

### 📸 Evidence Section
- Up to 6 evidence images per PDF
- Each image with filename caption
- Additional images reference available in evidence folder

---

## Output Directory Structure

```
reports/
├── student_reports/
│   ├── Student_ID_1_Report_20260419_103045.pdf
│   ├── Student_ID_2_Report_20260419_103045.pdf
│   ├── Student_ID_3_Report_20260419_103045.pdf
│   ├── index.html
│   └── index.html.bak
```

### Access Reports
1. **Via file browser**: `reports/student_reports/`
2. **Via HTML index**: Open `reports/student_reports/index.html` in browser
3. **Via API endpoint**: (Can add `/api/reports` endpoint)

---

## HTML Index Page

The system automatically generates `index.html` containing:
- 📊 Quick statistics (total reports, generation time)
- 📁 Clickable list of all student PDFs
- Direct download links
- Professional styling

---

## Data Format

### Detection Data Structure
```python
detection = {
    "timestamp": "HH:MM:SS",              # Time of detection
    "behavior_type": "Using Mobile 📱",   # Behavior description
    "confidence": 0.92,                   # Confidence score (0-1)
    "label": "Alert 🚨",                  # Alert level
    "situation": "using_mobile 📱 🚨"     # Emoji situation
}
```

### Evidence Image Structure
```python
evidence_images = [
    "evidence/ID1_101530.jpg",
    "evidence/ID1_101545.jpg"
]
```

---

## Risk Scoring Algorithm

```
Risk Score = 0 to 100

1. Alert-Level Events: +10 per event (max 40)
   - Example: 4 alerts = +40

2. Mobile Phone Detections: +30 (fixed)
   - Highest priority

3. Suspicious Events: +5 per event (max 20)
   - Example: 4 suspicious = +20

Risk Level Classification:
- 0-39:   🟢 LOW RISK (Green)
- 40-74:  🟡 MEDIUM RISK (Orange)
- 75-100: 🔴 HIGH RISK (Red)
```

---

## Features

### ✅ Automatic Features
- [x] Batch PDF generation for all students
- [x] Professional formatting
- [x] Color-coded risk levels
- [x] Timestamp tracking
- [x] Evidence image embedding
- [x] Behavior statistics
- [x] HTML index page generation
- [x] Configurable output directory

### ✅ Report Contents
- [x] Student identification
- [x] Detection timeline (20 most recent)
- [x] Behavior frequency breakdown
- [x] Risk assessment
- [x] Evidence gallery (up to 6 images)
- [x] Footer with generation details

### ✅ Customization
- [x] Custom output directory
- [x] Batch or single report generation
- [x] Evidence image inclusion
- [x] Configurable report fields

---

## Integration Steps

### Step 1: Import modules
```python
from student_report_integration import (
    initialize_student_reports,
    record_student_detection,
    record_student_evidence,
    generate_student_reports
)
```

### Step 2: Initialize on startup
```python
# In surveillance_loop or main
student_report_mgr = initialize_student_reports()
```

### Step 3: Record during surveillance
```python
# When detection occurs
record_student_detection(student_id, detection_data)

# When evidence is captured
record_student_evidence(student_id, image_path)
```

### Step 4: Generate at end
```python
# In finally block
generate_student_reports()
```

---

## Example Workflow

```python
# ==========================================
# INITIALIZATION
# ==========================================
from student_report_integration import (
    initialize_student_reports,
    record_student_detection,
    generate_student_reports
)

student_reports = initialize_student_reports()

# ==========================================
# DURING SURVEILLANCE
# ==========================================
# When student detected with mobile phone:
record_student_detection(1, {
    "timestamp": datetime.now().strftime("%H:%M:%S"),
    "behavior_type": "Using Mobile 📱",
    "confidence": 0.92,
    "label": "Alert 🚨",
    "situation": "using_mobile 📱 🚨"
})

# When evidence image captured:
record_student_evidence(1, "evidence/ID1_mobile_detection.jpg")

# ==========================================
# END OF SURVEILLANCE
# ==========================================
# Generate all student reports at end:
report_paths = generate_student_reports()

# Reports available at:
# reports/student_reports/Student_ID_1_Report_*.pdf
# reports/student_reports/index.html
```

---

## Command Line Usage

### Generate Test Reports
```bash
python student_detection_pdf_generator.py
```

### Generate Integration Reports
```bash
python student_report_integration.py
```

---

## Troubleshooting

### Issue: Images not appearing in PDF
**Solution:** Ensure image paths are correct and files exist
```python
import os
if not os.path.exists(image_path):
    print(f"⚠️ Image not found: {image_path}")
```

### Issue: PDF generation fails
**Solution:** Check ReportLab installation
```bash
pip install reportlab
```

### Issue: Access denied to output directory
**Solution:** Check folder permissions
```python
os.makedirs("reports/student_reports", exist_ok=True, mode=0o755)
```

---

## Performance Considerations

| Metric | Value |
|--------|-------|
| Time per report | ~2-5 seconds |
| PDF file size | 500KB - 2MB (with images) |
| Memory per report | ~10-50MB |
| Max images per PDF | 6 (embedded) |
| Batch generation | All students simultaneously |

---

## File Locations

| Component | Location |
|-----------|----------|
| PDF Reports | `reports/student_reports/` |
| HTML Index | `reports/student_reports/index.html` |
| Evidence Images | `evidence/` |
| Generator Code | `student_detection_pdf_generator.py` |
| Integration Code | `student_report_integration.py` |

---

## Next Steps

1. ✅ Place `student_detection_pdf_generator.py` in project root
2. ✅ Place `student_report_integration.py` in project root
3. ✅ Update `api_server.py` to integrate student report generation
4. ✅ Test with `python student_detection_pdf_generator.py`
5. ✅ Access reports via `reports/student_reports/index.html`
6. ✅ Distribute PDFs to administration

---

## Sample Output

### PDF Filename Format
```
Student_ID_{id}_Report_{YYYYMMDD}_{HHMMSS}.pdf

Example:
Student_ID_1_Report_20260419_103045.pdf
Student_ID_2_Report_20260419_103045.pdf
Student_ID_42_Report_20260419_103045.pdf
```

### Access URL
```
file:///D:/mini%20project/mini%20project/reports/student_reports/index.html
```

---

## Customization Options

### Change Output Directory
```python
generator = StudentDetectionReportGenerator(
    output_dir="custom_reports_path"
)
```

### Change Risk Thresholds
```python
# In risk_assessment section
if risk_score >= 80:  # Changed from 75
    risk_level = "🔴 HIGH RISK"
```

### Add Custom Footer
```python
# Edit _create_footer() method
elements.append(Paragraph(
    "© 2026 Educational Institution - Confidential",
    footer_style
))
```

---

## Summary

✅ **YES, PDF generation is fully possible!**

Your system now supports:
- Individual student detection PDFs
- Automatic batch generation
- HTML index page for easy access
- Risk scoring and assessment
- Evidence image embedding
- Professional formatting

Simply integrate the code and your surveillance system will generate professional PDF reports for each student automatically!

