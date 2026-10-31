import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime
from urllib.parse import urlparse, urlunparse
import requests
from google import genai
from google.genai import errors, types

# ==============================================================================
# ENVIRONMENT CREDENTIALS
# ==============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_URLS_FILE = os.path.join(BASE_DIR, "seen_urls.json")

# Blacklist domain spam/forum/aggregator
EXCLUDED_DOMAINS = [
    "reddit.com",
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "jaabz.com",
    "bookdomits.com",
    "ziprecruiter.com",
    "seek.com",
    "roberthalf.com",
    "youtube.com",
    "tiktok.com",
    "teamblind.com",
    "newsnowgh.com",
    "jooble.org",
]

# Master Profile terinjeksi dari data CV resmi
CANDIDATE_PROFILE = """
CANDIDATE: Muchamat Riyan Khamdani
EDUCATION: Bachelor of Applied Science in Internet Engineering Technology, Universitas Gadjah Mada (UGM)
CURRENT ROLE: Cloud Engineer at iZeno (March 2023 - Present)
- Architected & administered mission-critical Red Hat OpenShift & multi-cloud container environments (AWS/GCP) for tier-1 financial institutions (99.9% service availability).
- Automated end-to-end Disaster Recovery Center (DRC) provisioning using Terraform & Ansible (cut manual provisioning by 60%, strict RTO/RPO audit compliance).
- Operationalized containerized AI/LLM operational workflows on Dataiku DSS & Kubernetes/Podman (accelerated incident response by 40%), integrated securely across PostgreSQL, MySQL, and Oracle.
PREVIOUS ROLE: L2 Cloud Engineer at Datacomm Diangraha (March 2022 - Feb 2023)
- VMware vSphere, NSX-T, vCloud, Zerto failover testing, Acronis backup/restore, MikroTik routing.
TECHNICAL SKILLS:
- Linux (RHEL, Ubuntu, CentOS), AWS, Alibaba Cloud (ACA Certified), GCP, Terraform, Ansible, Docker, Podman, OpenShift, Kubernetes (GKE), Agentic AI, LLMs, Jenkins, Bamboo, Grafana, PostgreSQL, MySQL, Oracle, VMware, Zerto.
PREFERENCES: Fully Remote Worldwide (APAC/EMEA/Global), OR Onsite with Relocation/Visa Sponsorship in stable economies (Japan, UAE/GCC, Singapore, Western Europe).
"""


def normalize_url(raw_url: str) -> str:
    """Membersihkan URL dari query parameters dan trailing slash."""
    try:
        parsed = urlparse(raw_url)
        clean = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))
        return clean
    except Exception:
        return raw_url.strip().rstrip("/")


def generate_job_hash(title: str, clean_url: str) -> str:
    """Membuat signature unik dari title dan URL yang bersih."""
    unique_string = f"{title.lower().strip()}|{clean_url}"
    return hashlib.sha256(unique_string.encode()).hexdigest()


def load_seen_urls():
    """Membaca riwayat identifier yang pernah dikirim."""
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE, "r") as f:
                data = json.load(f)
                return set(data)
        except Exception as e:
            print(f"⚠️ Gagal membaca {SEEN_URLS_FILE}: {e}")
    return set()


def save_seen_urls(seen_urls):
    """Menyimpan riwayat identifier ke file JSON."""
    try:
        with open(SEEN_URLS_FILE, "w") as f:
            json.dump(list(seen_urls), f, indent=2)
        print(f"💾 Berhasil menyimpan {len(seen_urls)} data ke {SEEN_URLS_FILE}")
    except Exception as e:
        print(f"⚠️ Gagal menyimpan {SEEN_URLS_FILE}: {e}")


def is_job_active(url):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=8, allow_redirects=True)

        if response.status_code in [404, 410]:
            return False

        if response.status_code != 200:
            return any(
                ats in url
                for ats in ["greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com"]
            )

        expired_keywords = [
            "no longer accepting applications",
            "job has expired",
            "position has been filled",
            "this job is closed",
            "this role is no longer available",
            "page not found",
            "404 not found",
        ]

        content_lower = response.text.lower()
        if any(keyword in content_lower for keyword in expired_keywords):
            return False

        return True
    except Exception:
        return False


def search_tavily(query, domains=None):
    if not TAVILY_API_KEY:
        print("⚠️ Warning: TAVILY_API_KEY tidak ditemukan.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "topic": "general",
        "days": 2,
        "max_results": 15,
        "search_depth": "advanced",
    }

    if domains:
        payload["include_domains"] = domains

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            results = response.json().get("results", [])
            valid_jobs = []

            for r in results:
                link = r.get("url", "")

                if any(bad_domain in link.lower() for bad_domain in EXCLUDED_DOMAINS):
                    continue

                if is_job_active(link):
                    clean_url = normalize_url(link)
                    job_title = r.get("title", "Job Posting")
                    valid_jobs.append({
                        "title": job_title,
                        "url": link,
                        "clean_url": clean_url,
                        "hash": generate_job_hash(job_title, clean_url),
                        "snippet": r.get("content", "")[:450],
                    })
                else:
                    print(f"⏩ Skipping closed/expired job: {link}")

            return valid_jobs
        return []
    except Exception as e:
        print(f"❌ Error searching '{query}': {e}")
        return []


def get_job_postings(seen_hashes):
    # Fokus langsung ke domain ATS Tier-1 global
    ats_domains = [
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.ashbyhq.com",
        "jobs.smartrecruiters.com",
    ]

    # Query diperketat: buang lowongan non-remote US/EU dan filter tech stack target
    search_configs = [
        {
            "category": "REMOTE_GLOBAL",
            "query": (
                '("Site Reliability Engineer" OR "Cloud Platform Engineer" OR "Senior DevOps") '
                '("Worldwide" OR "Anywhere" OR "Remote - Global" OR "APAC" OR "Indonesia") '
                '("Kubernetes" OR "OpenShift" OR "Terraform") '
                '-"US only" -"Must be located in US" -"Security Clearance" -"EU only"'
            ),
            "domains": ats_domains,
        },
        {
            "category": "VISA_SPONSOR",
            "query": (
                '("Site Reliability Engineer" OR "Platform Engineer" OR "Cloud Engineer") '
                '("visa sponsorship" OR "relocation support") '
                '("Kubernetes" OR "Cloud Infrastructure") '
                '("Japan" OR "Dubai" OR "UAE" OR "Singapore" OR "Europe" OR "Germany")'
            ),
            "domains": ats_domains,
        },
    ]

    job_data = {"REMOTE_GLOBAL": [], "VISA_SPONSOR": []}
    print("🔎 Searching direct ATS links (Filtering duplicates & checking active status)...")

    for cfg in search_configs:
        results = search_tavily(cfg["query"], cfg["domains"])
        for item in results:
            job_hash = item["hash"]

            if job_hash in seen_hashes or item["clean_url"] in seen_hashes:
                continue

            if not any(existing["hash"] == job_hash for existing in job_data[cfg["category"]]):
                job_data[cfg["category"]].append(item)

    # Batasi maksimal 3 lowongan terbaik per kategori agar pesan Telegram padat dan tidak terpotong
    job_data["REMOTE_GLOBAL"] = job_data["REMOTE_GLOBAL"][:3]
    job_data["VISA_SPONSOR"] = job_data["VISA_SPONSOR"][:3]

    return job_data


def summarize_with_gemini(job_data, retries=3):
    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY tidak dikonfigurasi.")
        return None

    if not job_data["REMOTE_GLOBAL"] and not job_data["VISA_SPONSOR"]:
        print("ℹ️ Tidak ada lowongan baru yang lolos seleksi hari ini.")
        return None

    print("🤖 AI formatting direct job apply links with Gemini...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
You are an Executive Career Agent for Muchamat Riyan Khamdani.
Filter and synthesize these ATS job postings into an actionable Telegram card in Bahasa Indonesia.

CANDIDATE MASTER PROFILE:
{CANDIDATE_PROFILE}

RAW SCRAPED JOB DATA:
{job_data}

STRICT INSTRUCTIONS:
1. Divide into 2 sections:
   - 🌐 **LOWONGAN REMOTE GLOBAL (TAP-TO-APPLY)**
   - ✈️ **LOWONGAN VISA SPONSOR / RELOKASI**
2. STRICT ELIMINATION:
   - Discard roles requiring US/EU citizenship or mandatory local on-site attendance without visa support.
   - Discard roles with < 75% match against Riyan's profile.
3. FOR EACH VALID ROLE:
   - Header: 🔥 **[Match Score]% MATCH — [Judul Posisi - Perusahaan]**
   - 📍 Lokasi & 💰 Estimasi Gaji wajar (Contoh: $75,000 - $95,000 USD / tahun).
   - 📋 *Tap-to-copy Form Answer ("Why Us / Cover Pitch"):*
     Generate a 2-SENTENCE punchy, high-impact answer in English linking Riyan's tier-1 banking OpenShift/K8s resilience (99.9% uptime) and IaC automation to the target company's mission.
     ENCLOSE THIS 2-SENTENCE ANSWER STRICTLY INSIDE MONOSPACE CODE BLOCKS (```) so Riyan can tap to copy it in 1 second on Telegram mobile.
   - 🔗 Apply link: EXACT URL FROM DATA (Do not truncate or alter).
4. If a section has no qualifying jobs, write: "Belum ada lowongan dengan match tinggi hari ini."

OUTPUT FORMAT TEMPLATE:
💼 **DAILY JOB HUNTER DIGEST (ZERO-FRICTION)** 💼
====================================

🌐 **LOWONGAN REMOTE GLOBAL (TAP-TO-APPLY)**
- 🔥 **[Match Score]% MATCH — [Judul Posisi - Perusahaan]**
  📍 [Lokasi] | 💰 Est. Gaji: [Rentang USD]
  📋 *Jawaban form ("Why Us?"):*
  ```
  [2-sentence high-impact pitch]
  ```
  🔗 Apply: [URL]

✈️ **LOWONGAN VISA SPONSOR / RELOKASI**
- 🔥 **[Match Score]% MATCH — [Judul Posisi - Perusahaan]**
  📍 [Lokasi] | 💰 Est. Gaji: [Rentang USD]
  📋 *Jawaban form ("Why Us?"):*
  ```
  [2-sentence high-impact pitch]
  ```
  🔗 Apply: [URL]
"""

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
            )
            return response.text
        except Exception as e:
            print(f"⚠️ Gemini API attempt {attempt + 1} failed: {e}")
            time.sleep(2 * (attempt + 1))

    return None


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Error: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Pisahkan pesan jika melebihi batas 4000 karakter Telegram
    chunks = [message[i : i + 4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code != 200:
                # Fallback ke plain text jika ada formatting markdown yang tidak valid
                payload.pop("parse_mode", None)
                requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"❌ Gagal mengirim pesan ke Telegram: {e}")


def main():
    print("🚀 Starting Job Hunter Agent...")
    seen_urls = load_seen_urls()
    job_data = get_job_postings(seen_hashes=seen_urls)

    if not job_data["REMOTE_GLOBAL"] and not job_data["VISA_SPONSOR"]:
        print("ℹ️ Tidak ada lowongan baru hari ini. Selesai.")
        return

    summary = summarize_with_gemini(job_data)
    if summary:
        send_telegram(summary)
        print("✅ Notifikasi Telegram berhasil dikirim.")

        # Simpan hash dan URL bersih agar tidak terkirim duplikat di run berikutnya
        for cat in ["REMOTE_GLOBAL", "VISA_SPONSOR"]:
            for item in job_data[cat]:
                seen_urls.add(item["hash"])
                seen_urls.add(item["clean_url"])
        save_seen_urls(seen_urls)
    else:
        print("⚠️ Gagal membuat ringkasan lowongan dengan Gemini.")


if __name__ == "__main__":
    main()
