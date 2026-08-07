# Chrome Web Store Listing — Job Description Analyzer

> Last Updated: 2026-08-06

## Store Listing

**Extension Name**
Job Description Analyzer - AI Resume Matcher

**Short Description**
Compare job descriptions with your resume (PDF/DOCX/TXT). Get instant match score, skill gaps, and bullet rewrites.

**Detailed Description**
Job Description Analyzer is a smart productivity tool designed to help job seekers tailor their resumes for maximum ATS and recruiters match rate.

Select any job description text on any website (LinkedIn, Indeed, Greenhouse, Lever, Workday) and instantly analyze how well your resume matches the job requirements.

Key Features:
- Seamless Resume Support: Upload or drag-and-drop PDF, DOCX, or TXT resume documents.
- Floating Selection Action: Highlight job description text on any webpage to reveal a instant 'Analyze with Resume' action pill.
- Context Menu Integration: Right-click selected job description text to trigger analysis immediately.
- Comprehensive Match Score: Visual gauge for overall match %, technical skill coverage %, keyword similarity %, and semantic similarity.
- Skill Gap Analysis: Highlights missing key technologies and required qualifications missing from your resume.
- One-Click Resume Rewrites: Generates tailored bullet points incorporating missing skills ready to copy into your resume.
- Privacy First: Operates fully standalone in client-side mode with local file parsing.

How to Use:
1. Open the Job Description Analyzer side panel by clicking the extension icon.
2. Upload or drag-and-drop your resume (PDF, Word DOCX, or TXT format).
3. Highlight any job description text on a webpage and click 'Analyze with Resume'.
4. View your match score gauge, missing skill tags, and copy tailored bullet suggestions.

Privacy & Security:
Your resume files and job description text are parsed locally on your device. We respect user privacy and do not sell or track personal data.

Support & Feedback:
For questions or support, visit our open repository or submit feedback through our developer support portal.


**Category**
Productivity

**Single Purpose**
Compares selected webpage job descriptions against uploaded resumes to calculate match scores and skill suggestions.

**Primary Language**
English


## Graphics & Assets

| Asset | Dimensions | Status | Filename |
|-------|-----------|--------|----------|
| Store Icon [REQUIRED] | 128×128 PNG | ✅ Ready | `extension/icons/icon-128.png` |
| Screenshot 1 [REQUIRED] | 1280×800 or 640×400 | 🟡 Pending Capture | `screenshots/screenshot-1.png` |
| Screenshot 2 [RECOMMENDED] | 1280×800 or 640×400 | 🟡 Pending Capture | `screenshots/screenshot-2.png` |
| Small Promo Tile | 440×280 PNG | 🟡 Pending Capture | `screenshots/promo-tile.png` |


## Permissions Justification

Every permission in `manifest.json` is strictly required for core user-facing extension capabilities:

| Permission | Type | Justification |
|------------|------|---------------|
| `sidePanel` | permissions | Used to display the primary extension side panel UI containing the match score gauge, resume file manager, and skill suggestions. |
| `storage` | permissions | Used to persist user settings, backend API configuration, and extracted resume text locally in `chrome.storage.local`. |
| `contextMenus` | permissions | Used to add the right-click menu entry 'Analyze with Resume' for highlighted text on webpages. |
| `scripting` | permissions | Used to read the user's active text selection when clicking 'Grab Selection' inside the side panel. |
| `activeTab` | permissions | Used to interact with the currently active tab when the user initiates a job description analysis action. |
| `tabs` | permissions | Used to locate the active window tab ID when opening the side panel via context menu. |
| `<all_urls>` | host_permissions | Allows the content script to display the quick action selection pill on any job portal website (LinkedIn, Indeed, Lever, etc.). |


## Privacy & Data Use

### Data Collection
- **Does the extension collect user data?** No. Data is processed locally in the browser or via user's private local API server.

| Data Type | Collected? | Transmitted Off-Device? | Purpose | Shared with Third Parties? |
|-----------|-----------|------------------------|---------|---------------------------|
| Personally identifiable info | No | No | N/A | No |
| Website content | No | No (Local matching) | Analyzes job description text selected by user | No |
| User activity | No | No | N/A | No |

### Data Use Certification
- [x] Data is NOT sold to third parties
- [x] Data is NOT used for purposes unrelated to the extension's core functionality
- [x] Data is NOT used for creditworthiness or lending purposes


## Privacy Policy

**Privacy Policy URL**
`https://github.com/ashishk/jd-analyzer/blob/main/PRIVACY_POLICY.md`


## Distribution

- **Visibility**: Public
- **Regions**: All regions
- **Pricing**: Free


## Developer Info

- **Publisher Name**: Job Description Analyzer
- **Contact Email**: support@jdanalyzer.example.com
- **Homepage URL**: `https://github.com/ashishk/jd-analyzer`


## Step-by-Step Publishing Guide

### Step 1: Package the Extension ZIP File
Create a clean `.zip` archive containing ONLY the files in the `extension/` directory.

Run command in root folder:
```bash
cd extension && zip -r ../jd-analyzer-extension.zip . -x "*.DS_Store"
```

### Step 2: Open Chrome Developer Dashboard
1. Go to the [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole).
2. Sign in with your Google account. (If it's your first time, pay the one-time $5 developer registration fee).

### Step 3: Create New Item
1. Click the **Add new item** button in the top right.
2. Upload the `jd-analyzer-extension.zip` file created in Step 1.

### Step 4: Fill Store Listing Details
Copy and paste the exact information from this document (`CHROMEWEBSTORE.md`):
- Name: `Job Description Analyzer - AI Resume Matcher`
- Short description & Detailed description
- Category: `Productivity`
- Single Purpose description

### Step 5: Upload Visual Assets
- Upload Store Icon: `extension/icons/icon-128.png`
- Upload at least 1 screenshot (1280x800 or 640x400 PNG/JPEG) showing the extension side panel and floating action pill in action.

### Step 6: Complete Privacy & Justifications Tab
- Enter the Privacy Policy URL.
- Copy and paste the **Permissions Justification** table items above for `sidePanel`, `storage`, `contextMenus`, `scripting`, `activeTab`, `tabs`, and `<all_urls>`.
- Check the Data Use certifications.

### Step 7: Submit for Review
1. Click **Submit for review**.
2. Chrome extension review usually takes 24 to 72 hours. Once approved, your extension will be published live on the Chrome Web Store!
