# 💼 Job Hunter Agent: Automated Global Job Digest Powered by Google Gemini API

An automated, serverless AI agent designed to solve information overload for software engineers searching for global remote and visa-sponsored SRE/DevOps roles. Powered by **Google Gemini API** (`google-genai` SDK) and **GitHub Actions**.

## 📌 Background & Problem Statement
For software engineers and IT professionals in the APAC region, discovering legitimate global remote opportunities (USD/GBP compensation) or roles offering explicit visa sponsorship is a time-consuming challenge. Job boards are often flooded with irrelevant listings, regional hiring caps, or non-sponsoring companies. Manual filtering takes hours of daily research.

## 🚀 Solution & Key Features
**Job Hunter Agent** automates the entire job discovery and filtering lifecycle:
* **Intelligent AI Filtering:** Uses Google Gemini API (`gemini-3.6-flash`) to analyze unstructured job postings, evaluate candidates' core tech stacks (Kubernetes, GCP, IaC, Python), and extract valid visa sponsorship details.
* **Serverless Cron Automation:** Runs on a scheduled workflow via GitHub Actions without requiring 24/7 dedicated server overhead.
* **Resilient Infrastructure:** Features automated exponential backoff with randomized jitter to handle transient API capacity limits and rate throttling smoothly.
* **Instant Telegram Delivery:** Formats and pushes curated daily digests directly to a private Telegram channel, complete with state-based deduplication (`seen_urls.json`).

---

## 📱 Sample Output (Telegram Notification)
Below is an actual daily digest delivered by the agent directly to Telegram:

```text
💼 DAILY JOB HUNTER DIGEST 💼
====================================

🌐 LOWONGAN REMOTE GLOBAL (24H FRESH)
• Site Reliability Engineer - Canonical
  Membutuhkan latar belakang kuat di bidang Linux, Python, networking, dan Kubernetes dari tingkat bare-metal hingga cloud.
  🔗 Apply disini: http://job-boards.greenhouse.io/canonical/jobs/4468036

• Senior DevOps / Site Reliability Engineer - Stellar Cyber
  Fokus pada pembangunan, pengoperasian, dan penskalaan infrastruktur cloud-native serta platform data terdistribusi.
  🔗 Apply disini: https://apply.workable.com/stellar-cyber/j/B82B36D73C

✈️ LOWONGAN VISA SPONSOR / RELOKASI
• DevOps Engineer (Visa Sponsorship) - JobMetasearch
  Kumpulan posisi DevOps dengan sponsor visa yang berfokus pada ekosistem Kubernetes, AWS, dan CI/CD.
  🔗 Apply disini: https://jobmetasearch.ai/visa-sponsorship/devops-engineer

• DevOps Engineer - Hunt UK Visa Sponsors
  Peluang karir DevOps Engineer di Inggris (London dan Belfast) dengan dukungan penuh UK Visa Sponsorship.
  🔗 Apply disini: https://huntukvisasponsors.com/jobs/role/devops-engineer
🏗️ Architecture & Tech Stack
LLM Engine: Google Gemini API (google-genai Python SDK)

Search & Scraping: Tavily Search API (ATS Domain Filtered: Greenhouse, Lever, Workable, SmartRecruiters)

Orchestration: GitHub Actions (job_agent.yml)

Notification: Telegram Bot API

Language: Python 3.11+
