# 💼 Job Hunter Agent: Automated Global Job Digest Powered by Google Gemini API

## 📌 Background & Local Problem
For software engineers and tech professionals in the APAC region, discovering legitimate global remote opportunities (USD/GBP compensation) or roles with explicit visa sponsorship is a time-consuming challenge. Job boards are often flooded with irrelevant listings, regional hiring caps, or non-sponsoring companies. Manual filtering takes hours of daily research.

## 🚀 The Solution
**Job Hunter Agent** is an open-source, zero-cost serverless AI agent that automates the entire job discovery process. Built using the **Google Gemini API SDK (`google-genai`)** and **GitHub Actions**, the agent runs on a daily schedule to fetch job feeds, evaluate job specifications against structured candidate criteria, and push a curated *Daily Job Digest* directly to Telegram.

## 🛠️ How Google AI Tools Were Used
* **Model Integration:** Utilized `gemini-3.6-flash` via the official `google-genai` Python SDK for fast, accurate text summarization and information extraction.
* **Prompt Engineering:** Structured prompts instruct Gemini to analyze raw job data, extract key tech stacks (GCP, Kubernetes, Terraform, Python), verify visa sponsorship/remote conditions, and format direct application URLs without hallucination.
* **Production Resilience:** Implemented exponential backoff with randomized jitter to gracefully handle transient API capacity limits and rate throttling.

## 🏗️ Architecture
1. **Trigger:** Scheduled cron job via GitHub Actions (`job_agent.yml`).
2. **Data Fetching:** Python orchestrator (`agent.py`) queries direct ATS job postings (Greenhouse, Lever, Workable).
3. **AI Reasoning:** Raw job data is passed to Google Gemini API to produce formatted Markdown summaries.
4. **Delivery & Deduplication:** Telegram Bot API pushes the daily digest, while `seen_urls.json` prevents duplicate notifications.

## 📈 Impact
* Eliminates 10+ hours of manual job search weekly for APAC developers looking for global roles.
* Delivers high-precision, actionable opportunities directly to mobile devices every single morning.
