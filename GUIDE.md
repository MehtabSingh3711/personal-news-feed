# Personal Intelligence Engine — Deployment & Setup Guide

This guide explains step-by-step how to publish your Personal Intelligence Engine codebase to GitHub, configure GitHub Actions for automatic updates every 6 hours, set up GitHub Pages, and subscribe to your personal feed in **Reeder on iPhone**.

---

## Step 1: Create a GitHub Repository

1. Go to [GitHub New Repository](https://github.com/new).
2. Name the repository: `personal-news-feed` (or your preferred name).
3. Choose **Public** (required for GitHub Pages free tier).
4. Do **NOT** initialize with a README, .gitignore, or License (these are already created).
5. Click **Create repository**.

---

## Step 2: Push Your Code to GitHub

Open terminal / PowerShell in the project directory (`c:\Users\mehta\Downloads\personal-news-feed`) and run:

```bash
# Initialize git if not already initialized
git init

# Add all project files
git add .

# Initial commit
git commit -m "Initial commit: Personal Intelligence Engine"

# Set main branch
git branch -M main

# Add your GitHub repository remote (replace with YOUR username)
git remote add origin https://github.com/YOUR_USERNAME/personal-news-feed.git

# Push to GitHub
git push -u origin main
```

---

## Step 3: Configure GitHub Secrets (Optional APIs)

The pipeline works 100% deterministically without API keys. However, if you want LLM second-stage judging or higher Semantic Scholar rate limits:

1. In your GitHub repository, go to **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret**.
3. Add any of the following optional secrets:

| Secret Name | Value Example | Description |
|-------------|---------------|-------------|
| `LLM_API_KEY` | `AIzaSy...` | Gemini API Key (or OpenAI key) |
| `LLM_PROVIDER` | `gemini` | `gemini` or `openai` |
| `LLM_MODEL` | `gemini-2.5-flash` | Model identifier |
| `LLM_ENABLED` | `true` | Set to `true` to enable 2nd-stage LLM judge |
| `SEMANTIC_SCHOLAR_API_KEY` | `your_key` | Optional S2 API key for higher rate limits |

---

## Step 4: Your Live GitHub Pages Feed URL

Your GitHub Pages deployment is **SUCCESSFUL** and live at:

```text
https://mehtabsingh3711.github.io/personal-news-feed/feed.xml
```

---

## Step 5: Test GitHub Actions Manual Run

1. In your GitHub repository, click on the **Actions** tab.
2. Select **Update Intelligence Feed** from the left sidebar.
3. Click **Run workflow** → **Run workflow**.
4. The workflow will run, ingest all 25+ live sources, remove noise/duplicates, score events, and push an updated `feed.xml` back to your repo.
5. Going forward, GitHub Actions will automatically run this workflow **every 6 hours**.

---

## Step 6: Subscribe in Reeder on iPhone

1. Copy your live feed URL:
   ```text
   https://mehtabsingh3711.github.io/personal-news-feed/feed.xml
   ```
2. Open **Reeder** on your iPhone.
3. Tap **+** (Add Feed / Subscription).
4. Paste the URL above.
5. Tap **Add**.

---

## How It Works in Reeder

Your feed will present a curated briefing:

```text
PERSONAL INTELLIGENCE

[9.7] NVIDIA launches new AI platform
      Technology / AI Research

[9.5] India-EU reach major trade breakthrough
      Geopolitics / Trade

[9.3] Fed signals major monetary policy shift
      Global Markets / Central Banks

[9.1] New reasoning architecture achieves major benchmark gains
      AI Research / LLM
```

Each article contains:
- **WHAT HAPPENED**: Concise 2–4 sentence summary
- **WHY IT MATTERS**: Key implications
- **IMPORTANCE**: Final score (0–10) & Classification (`MUST READ` / `WORTH KNOWING`)
- **CATEGORIES**: Taxonomy tags
- **SOURCES**: Cross-source confirmation list
- **SIGNALS**: HF upvotes, GitHub stars, citations, paper venue
