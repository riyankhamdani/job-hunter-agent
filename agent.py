from datetime import datetime
import json
import os
import sys
from google import genai
import requests

# Credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_URLS_FILE = "seen_urls.json"

CANDIDATE_PROFILE = """
Candidate Name: Muchamat Riyan Khamdani
Education: Bachelor of Applied Science in Internet Engineering Technology (UGM)
Current Role: Cloud Engineer at Izeno (Prev: L2 Cloud Engineer at Datacomm Diangraha)
Tech Stack: AWS, GCP, Alibaba Cloud (ACA Certified), Terraform, Ansible, Docker, Podman, OpenShift, Kubernetes (GKE), AI Agents, LLM, Jenkins, Bamboo, Grafana, PostgreSQL, MySQL, Oracle, VMware vSphere, NSX-T, Zerto.
Target Roles: Cloud Engineer, DevOps Engineer, Site Reliability Engineer (SRE), Infrastructure Engineer.
Preferences: Fully Remote Worldwide, OR Onsite with Visa Sponsorship/Relocation in Stable Countries.
"""


def load_seen_urls():
    """Membaca riwayat URL yang pernah dikirim."""
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"⚠️ Gagal membaca {SEEN_URLS_FILE}: {e}")
    return set()


def save_seen_urls(seen_urls):
    """Menyimpan riwayat URL baru ke file JSON."""
    try:
        with open(SEEN_URLS_FILE, "w") as f:
            json.dump(list(seen_urls), f, indent=2)
    except Exception as e:
        print(f"⚠️ Gagal menyimpan {SEEN_URLS_FILE}: {e}")


def search_tavily(query, domains=None):
    if not TAVILY_API_KEY:
        print("⚠️ Warning: TAVILY_API_KEY tidak ditemukan.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "topic": "general",
        "days": 1,
        "max_results": 20,
        "search_depth": "advanced",
    }

    if domains:
        payload["include_domains"] = domains

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            results = response.json().get("results", [])
            valid_jobs = []

            allowed_domains = [
                "greenhouse.io",
                "jobs.lever.co",
                "apply.workable.com",
                "jobs.smartrecruiters.com",
                "ashbyhq.com",
                "linkedin.com/jobs/view",
                "hatch.co",
                "bamboohr.com",
            ]

            for r in results:
                link = r.get("url", "")

                if domains:
                    is_valid = any(domain in link for domain in allowed_domains)
                else:
                    is_valid = (
                        len(link.split("/")) > 3
                        and not link.endswith("/jobs")
                        and not link.endswith("/search")
                        and "q-" not in link
                    )

                if is_valid:
                    valid_jobs.append({
                        "title": r.get("title", "Job Posting"),
                        "url": link,
                        "snippet": r.get("content", "")[:300],
                    })

            return valid_jobs
        return []
    except Exception as e:
        print(f"❌ Error searching '{query}': {e}")
        return []


def get_job_postings(seen_urls):
    ats_domains = [
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "jobs.lever.co",
        "apply.workable.com",
        "ashbyhq.com",
        "jobs.smartrecruiters.com",
    ]

    search_configs = [
        {
            "category": "REMOTE_GLOBAL",
            "query": (
                '("DevOps" OR "Site Reliability Engineer" OR "Kubernetes") "Remote Worldwide"'
                " -salesforce -apex"
            ),
            "domains": ats_domains,
        },
        {
            "category": "REMOTE_GLOBAL",
            "query": (
                '("Cloud Engineer" OR "Infrastructure Engineer") "Remote"'
                ' ("Terraform" OR "GKE" OR "OpenShift") -salesforce'
            ),
            "domains": ats_domains,
        },
        {
            "category": "VISA_SPONSOR",
            "query": (
                '("DevOps" OR "Cloud Engineer" OR "SRE") "visa sponsorship" (Europe OR UK'
                " OR Japan OR Singapore)"
            ),
            "domains": None,
        },
        {
            "category": "VISA_SPONSOR",
            "query": (
                '("DevOps" OR "SRE" OR "Platform Engineer") "relocation" (Netherlands OR'
                " Japan OR Switzerland OR Germany)"
            ),
            "domains": None,
        },
    ]

    job_data = {"REMOTE_GLOBAL": [], "VISA_SPONSOR": []}
    print("🔎 Searching direct job apply links (Filtering duplicates)...")

    for cfg in search_configs:
        results = search_tavily(cfg["query"], cfg["domains"])
        for item in results:
            url = item["url"]

            if url in seen_urls:
                continue

            if not any(
                existing["url"] == url for existing in job_data[cfg["category"]]
            ):
                job_data[cfg["category"]].append(item)

    job_data["REMOTE_GLOBAL"] = job_data["REMOTE_GLOBAL"][:4]
    job_data["VISA_SPONSOR"] = job_data["VISA_SPONSOR"][:4]

    return job_data


def summarize_with_gemini(job_data):
    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY tidak dikonfigurasi.")
        return None

    if not job_data["REMOTE_GLOBAL"] and not job_data["VISA_SPONSOR"]:
        print("ℹ️ Tidak ada lowongan baru hari ini.")
        return None

    print("🤖 AI formatting direct job apply links with Gemini...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
    You are an Executive Career Agent for Riyan.
    Summarize these specific job postings in Bahasa Indonesia matching Riyan's profile.

    CANDIDATE PROFILE:
    {CANDIDATE_PROFILE}

    RAW JOB DATA:
    {job_data}

    INSTRUCTIONS:
    1. Group into 2 sections:
       - 🌐 **LOWONGAN REMOTE GLOBAL (24 JAM TERAKHIR)**
       - ✈️ **LOWONGAN VISA SPONSOR / RELOKASI (NEGARA STABIL)**
    2. Filter out any job from geopolitically unstable countries.
    3. If VISA_SPONSOR or REMOTE_GLOBAL has no results in RAW JOB DATA, write: "Belum ada update lowongan baru hari ini." for that section.
    4. For each valid job, output ONLY:
       - Bold Job Title & Company Name
       - 1 short sentence summarizing key requirements/tech stack matching Riyan
       - The EXACT direct application link provided in the raw data.
    5. ABSOLUTE RULE FOR URL: Copy the exact full "url" string provided in the raw data without altering it.

    Format template:
    💼 **DAILY JOB HUNTER DIGEST** 💼
    ====================================

    🌐 **LOWONGAN REMOTE GLOBAL (24H FRESH)**
    • **[Judul Posisi - Perusahaan]**
      [Ringkasan 1 kalimat syarat/tech stack]
      🔗 Apply disini: [EXACT_URL_FROM_DATA]

    ✈️ **LOWONGAN VISA SPONSOR / RELOKASI**
    • **[Judul Posisi - Perusahaan]**
      [Ringkasan 1 kalimat syarat/tech stack]
      🔗 Apply disini: [EXACT_URL_FROM_DATA]
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash", contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"❌ Summarizer Error: {e}")
        return None


def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials missing!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
        "parse_mode": "Markdown",
    }

    res = requests.post(url, json=payload, timeout=10)

    if res.status_code != 200:
        print(f"⚠️ Telegram Markdown Error: {res.text}. Retrying plain text...")
        payload.pop("parse_mode", None)
        res = requests.post(url, json=payload, timeout=10)

    if res.status_code == 200:
        print("🚀 Direct Job Digest successfully sent to Telegram!")
        return True
    else:
        print(f"❌ Telegram Send Failed: {res.text}")
        return False


if __name__ == "__main__":
    seen_urls = load_seen_urls()
    raw_jobs = get_job_postings(seen_urls)

    summary = summarize_with_gemini(raw_jobs)

    if summary:
        success = send_telegram(summary)
        if success:
            new_sent_urls = [
                job["url"]
                for cat in ["REMOTE_GLOBAL", "VISA_SPONSOR"]
                for job in raw_jobs[cat]
            ]
            seen_urls.update(new_sent_urls)
            save_seen_urls(seen_urls)
        else:
            sys.exit(1)
    else:
        print("ℹ️ Tidak ada pesan terkirim karena tidak ada lowongan baru.")
