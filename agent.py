from datetime import datetime
import json
import os
import random
import sys
import time
import requests
from google import genai
from google.genai import types, errors

# Credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_URLS_FILE = "seen_urls.json"

# Blacklist domain spam/forum/aggregator kotor
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
]

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


def is_job_active(url):
    """
    Mengecek apakah URL lowongan masih aktif (HTTP 200)
    dan tidak berisi teks bahwa pendaftaran sudah ditutup.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)

        if response.status_code != 200:
            return False

        expired_keywords = [
            "no longer accepting applications",
            "job has expired",
            "position has been filled",
            "this job is closed",
            "page not found",
            "404 not found",
            "this role is no longer available",
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
        "days": 1,  # Filter ketat 24 jam terakhir
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

                if any(bad_domain in link.lower() for bad_domain in EXCLUDED_DOMAINS):
                    continue

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
                    if is_job_active(link):
                        valid_jobs.append({
                            "title": r.get("title", "Job Posting"),
                            "url": link,
                            "snippet": r.get("content", "")[:300],
                        })
                    else:
                        print(f"⏩ Skipping closed/expired job: {link}")

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
