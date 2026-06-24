# TYC Member Tracking System — Setup Guide

## What's included
| File | Purpose |
|------|---------|
| `index.html` | Member tracker — host on GitHub Pages |
| `tyc_bot.py` | Discord bot — deploy to Railway |
| `apps_script.js` | Google Apps Script — paste into Google Sheets (form + bot endpoint) |
| `requirements.txt` | Python dependencies for the bot |
| `railway.toml` | Railway deployment config |

---

## Part 1 — Google Sheet + Form + Apps Script

### 1a. Set up the sheet
1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1_6XtYnKOUHwysLJS0Fq7ai_fFGvnNfaJ_whIJ_s0Wbc
2. Make sure it has a tab called **Members** with these headers in row 1:
   `ID | Name | Email | Phone | Discord | Province | Chapter | Role | Status | DiscordSynced | Joined`
   (The script will create this tab automatically if it doesn't exist.)

### 1b. Paste the Apps Script
1. In your sheet: **Extensions → Apps Script**
2. Delete any existing code
3. Paste the entire contents of `apps_script.js`
4. Click **Save**

### 1c. Create the Google Form (run ONCE)
1. In the Apps Script editor, select the function `createMemberForm` from the dropdown
2. Click **Run**
3. Grant permissions when prompted
4. A popup will appear with the **public form URL** — share this with applicants
5. A new tab called **Form Responses 1** will appear in your sheet
6. From now on, every form submission automatically adds a **Pending** row to the Members sheet

### 1d. Deploy as Web App (for the Discord bot)
1. Click **Deploy → New Deployment**
2. Type: **Web app**
3. Execute as: **Me**
4. Who has access: **Anyone**
5. Click **Deploy** → copy the **Web App URL**
6. Paste that URL into TYC Tracker → **Settings → Google Sheets Sync URL**

---

## Part 2 — Discord Bot

### Create the bot
1. Go to https://discord.com/developers/applications
2. Click **New Application** → name it "TYC Bot"
3. Go to **Bot** tab → **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - ✅ Server Members Intent
5. Copy the **Token** (keep this secret — never commit to GitHub)
6. Go to **OAuth2 → URL Generator**
   - Scopes: `bot`
   - Bot Permissions: `Manage Roles`, `View Channels`
7. Open the generated URL and invite the bot to **all 7 servers** (national + 6 provincial)

### Get server IDs
1. Discord **Settings → Advanced** → enable **Developer Mode**
2. Right-click each server icon → **Copy Server ID**

### Deploy to Railway
1. Push these files to a **private** GitHub repo:
   - `tyc_bot.py`
   - `requirements.txt`
   - `railway.toml`
2. Go to https://railway.com → **New Project → Deploy from GitHub repo**
3. Select your repo
4. Go to your service → **Variables** tab → add:

| Variable | Value |
|----------|-------|
| `DISCORD_BOT_TOKEN` | Your bot token |
| `SHEETS_URL` | Your Apps Script Web App URL |
| `NATIONAL_SERVER_ID` | Discord ID of the national TYC server |
| `SERVER_ONTARIO` | Discord ID of the Ontario server |
| `SERVER_NOVA_SCOTIA` | Discord ID of the Nova Scotia server |
| `SERVER_QUEBEC` | Discord ID of the Quebec server |
| `SERVER_NEW_BRUNSWICK` | Discord ID of the New Brunswick server |
| `SERVER_ALBERTA` | Discord ID of the Alberta server |
| `SERVER_SASKATCHEWAN` | Discord ID of the Saskatchewan server |

5. Click **Deploy** — Railway runs the bot 24/7

---

## Part 3 — TYC Tracker (GitHub Pages)

1. Create a GitHub repo (e.g. `tyc-tracker`) — keep it **private** if possible
2. Upload `index.html` (keep it named `index.html`)
3. Repo **Settings → Pages → Deploy from branch → main → / (root)**
4. Live at: `https://yourusername.github.io/tyc-tracker`

---

## Full flow

```
Applicant fills Google Form (public URL)
        ↓
Apps Script auto-adds row to Members sheet (Status = Pending)
        ↓
C-Suite / Provincial President logs into TYC Tracker
        ↓
Clicks "Approve" on pending member
        ↓
Status → Active, DiscordSynced → No
        ↓
Railway bot polls Sheet every 2 min
        ↓
Bot finds Active + unsynced member
        ↓
Assigns role in Provincial server + National server
        ↓
Sheet updated: DiscordSynced → Yes
```

---

## Discord Role Setup

Create these roles in **each** server (national + all 6 provincial):
- `C-Suite`
- `Provincial President`
- `Municipal Executive`
- `Member`

The **TYC Bot** role must be ranked **above** all of these in the role list.

---

## Default admin accounts — change immediately

| Username | Password | Role |
|----------|----------|------|
| `xavier` | `tyc2024!` | C-Suite |
| `amayas` | `tyc2024!` | C-Suite |

Change in **Tracker → Settings → Admin Accounts**.
