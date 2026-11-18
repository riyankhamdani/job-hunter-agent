import hashlib
import html
import json
import os
import re
import time
from urllib.parse import urlparse, urlunparse
from google import genai
import requests

# ==============================================================================
# ENVIRONMENT CREDENTIALS
# ==============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_URLS_FILE = os.path.join(BASE_DIR, "seen_urls.json")

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
    "jobgether.com",
]

# Case-sensitive agar kata umum ("in", "or", "me", "ok") tidak salah deteksi
US_STATE_PATTERN = re.compile(
    r",\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b"
)

US_REMOTE_PATTERNS = [
    "us only",
    "u.s. only",
    "united states only",
    "us-based",
    "u.s.-based",
    "remote - us",
    "remote (us)",
    "remote, us",
    "us remote",
    "u.s. remote",
    "must be located in the us",
    "must reside in the us",
    "authorized to work in the united states",
    "authorized to work in the u.s.",
    "north america only",
    "americas only",
]

DISQUALIFIED_KEYWORDS_GLOBAL = US_REMOTE_PATTERNS + [
    "us citizenship",
    "green card",
    "security clearance",
    "secret clearance",
    "ts/sci",
    "itar",
    "w2 only",
    "no c2c",
    "uk only",
    "eu only",
    "europe only",
    "canada only",
    "latam only",
    "emea only",
    "hybrid",
    "on-site",
    "onsite",
]

DISQUALIFIED_KEYWORDS_SPONSOR = [
    "no sponsorship",
    "no visa sponsorship",
    "cannot sponsor",
    "unable to sponsor",
    "do not sponsor",
    "will not sponsor",
    "not eligible for sponsorship",
    "without sponsorship",
    "must have existing right to work",
    "security clearance",
    "secret clearance",
    "itar",
    "us citizenship required",
    "us citizens only",
]

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
PREFERENCES: Fully Remote Worldwide (APAC/Global), OR Onsite with Global Relocation / Visa Sponsorship (Japan, UAE/GCC, Singapore, Europe, Australia, etc.).
"""


def normalize_url(raw_url: str) -> str:
  try:
    parsed = urlparse(raw_url)
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/"),
        "",
        "",
        "",
    ))
  except Exception:
    return raw_url.strip().rstrip("/")


def generate_job_hash(title: str, clean_url: str) -> str:
  unique_string = f"{title.lower().strip()}|{clean_url}"
  return hashlib.sha256(unique_string.encode()).hexdigest()


def load_seen_urls() -> set:
  if os.path.exists(SEEN_URLS_FILE):
    try:
      with open(SEEN_URLS_FILE, "r") as f:
        return set(json.load(f))
    except Exception as e:
      print(f"⚠️ Gagal membaca {SEEN_URLS_FILE}: {e}")
  return set()


def save_seen_urls(seen_urls: set):
  try:
    with open(SEEN_URLS_FILE, "w") as f:
      json.dump(list(seen_urls), f, indent=2)
    print(f"💾 Berhasil menyimpan {len(seen_urls)} data ke {SEEN_URLS_FILE}")
  except Exception as e:
    print(f"⚠️ Gagal menyimpan {SEEN_URLS_FILE}: {e}")


def extract_visible_text(raw_html: str) -> str:
  """Membuang script/style/tag HTML agar pengecekan status lowongan akurat."""
  no_scripts = re.sub(
      r"<(script|style|noscript)[^>]*>.*?</\1>",
      " ",
      raw_html,
      flags=re.DOTALL | re.IGNORECASE,
  )
  no_tags = re.sub(r"<[^>]+>", " ", no_scripts)
  return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()


def fetch_and_validate_job(url: str) -> tuple[bool, str]:
  """Memeriksa apakah lowongan aktif dan mengambil teks bersih halaman ATS."""
  try:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

    if response.status_code in [404, 410]:
      return False, ""

    if response.status_code != 200:
      is_ats = any(
          ats in url
          for ats in [
              "greenhouse.io",
              "lever.co",
              "ashbyhq.com",
              "smartrecruiters.com",
              "workable.com",
          ]
      )
      return is_ats, ""

    visible_text = extract_visible_text(response.text)
    visible_lower = visible_text.lower()

    expired_keywords = [
        "no longer accepting applications",
        "job has expired",
        "position has been filled",
        "this job is closed",
        "this role is no longer available",
        "page not found",
        "404 not found",
    ]
    if any(keyword in visible_lower for keyword in expired_keywords):
      return False, ""

    return True, visible_text[:3500]
  except Exception:
    return False, ""


def is_disqualified_job(title: str, text_body: str, category: str) -> bool:
  """Filter lokal memakai judul + isi asli halaman ATS."""
  combined_raw = f"{title}\n{text_body}"
  combined_lower = combined_raw.lower()

  if category == "REMOTE_GLOBAL":
    if US_STATE_PATTERN.search(combined_raw):
      return True
    if any(bad_kw in combined_lower for bad_kw in DISQUALIFIED_KEYWORDS_GLOBAL):
      return True

  elif category == "VISA_SPONSOR":
    if any(bad_kw in combined_lower for bad_kw in DISQUALIFIED_KEYWORDS_SPONSOR):
      return True

  return False


def search_tavily(query: str, domains: list[str], seen_hashes: set) -> list[dict]:
  if not TAVILY_API_KEY:
    print("⚠️ Warning: TAVILY_API_KEY tidak ditemukan.")
    return []

  url = "https://api.tavily.com/search"
  payload = {
      "api_key": TAVILY_API_KEY,
      "query": query,
      "topic": "general",
      "days": 7,
      "max_results": 15,
      "search_depth": "advanced",
      "include_domains": domains,
  }

  try:
    response = requests.post(url, json=payload, timeout=20)
    if response.status_code != 200:
      return []

    results = response.json().get("results", [])
    valid_jobs = []

    for r in results:
      link = r.get("url", "")
      if not link or any(bad in link.lower() for bad in EXCLUDED_DOMAINS):
        continue

      clean_url = normalize_url(link)
      job_title = r.get("title", "Job Posting")
      job_hash = generate_job_hash(job_title, clean_url)

      # Cek duplikat SEBELUM melakukan HTTP GET ke portal ATS
      if job_hash in seen_hashes or clean_url in seen_hashes:
        continue

      is_active, page_text = fetch_and_validate_job(link)
      if is_active:
        full_context = page_text if len(page_text) > 200 else r.get("content", "")
        valid_jobs.append({
            "title": job_title,
            "url": link,
            "clean_url": clean_url,
            "hash": job_hash,
            "snippet": full_context[:1500],
        })
      else:
        print(f"⏩ Skipping closed/expired job: {link}")

    return valid_jobs
  except Exception as e:
    print(f"❌ Error searching '{query}': {e}")
    return []


def get_job_postings(seen_hashes: set) -> dict:
  ats_domains = [
      "boards.greenhouse.io",
      "job-boards.greenhouse.io",
      "jobs.lever.co",
      "jobs.ashbyhq.com",
      "jobs.smartrecruiters.com",
      "apply.workable.com",
  ]

  search_configs = [
      {
          "category": "REMOTE_GLOBAL",
          "query": (
              '("Site Reliability Engineer" OR "DevOps Engineer" OR "Cloud'
              ' Engineer" OR "Platform Engineer") ("Remote" AND ("Worldwide" OR'
              ' "Anywhere" OR "APAC" OR "Global")) ("Kubernetes" OR "Terraform"'
              ' OR "AWS") -"US only" -"United States only"'
          ),
          "domains": ats_domains,
      },
      {
          "category": "VISA_SPONSOR",
          "query": (
              '("Site Reliability Engineer" OR "DevOps Engineer" OR "Cloud'
              ' Engineer" OR "Platform Engineer") ("visa sponsorship" OR'
              ' "relocation package" OR "relocation assistance" OR "relocation'
              ' support") ("Kubernetes" OR "Cloud" OR "Terraform")'
          ),
          "domains": ats_domains,
      },
  ]

  job_data = {"REMOTE_GLOBAL": [], "VISA_SPONSOR": []}
  print("🔎 Searching direct ATS links (Filtering duplicates & checking active status)...")

  for cfg in search_configs:
    cat = cfg["category"]
    results = search_tavily(cfg["query"], cfg["domains"], seen_hashes)

    for item in results:
      if is_disqualified_job(item["title"], item["snippet"], cat):
        print(f"🚫 Eliminated (Disqualified by local filter): {item['title']}")
        continue

      if not any(existing["hash"] == item["hash"] for existing in job_data[cat]):
        job_data[cat].append(item)

    job_data[cat] = job_data[cat][:3]

  return job_data


def format_jobs_raw_fallback(job_data: dict) -> str:
  lines = [
      "💼 <b>DAILY JOB HUNTER DIGEST (RAW FALLBACK)</b> 💼",
      "====================================",
      "⚠️ <i>Catatan: AI formatter sedang cooldown, menampilkan tautan langsung.</i>\n",
  ]

  lines.append("🌐 <b>LOWONGAN REMOTE GLOBAL (TAP-TO-APPLY)</b>")
  if job_data.get("REMOTE_GLOBAL"):
    for j in job_data["REMOTE_GLOBAL"]:
      lines.append(f"🔥 <b>{html.escape(j['title'])}</b>")
      lines.append(f"🔗 Apply: {html.escape(j['url'])}\n")
  else:
    lines.append("Belum ada lowongan dengan match tinggi hari ini.\n")

  lines.append("✈️ <b>LOWONGAN VISA SPONSOR / RELOKASI GLOBAL</b>")
  if job_data.get("VISA_SPONSOR"):
    for j in job_data["VISA_SPONSOR"]:
      lines.append(f"🔥 <b>{html.escape(j['title'])}</b>")
      lines.append(f"🔗 Apply: {html.escape(j['url'])}\n")
  else:
    lines.append("Belum ada lowongan dengan match tinggi hari ini.\n")

  return "\n".join(lines)


def summarize_with_gemini(job_data: dict, retries: int = 2) -> str | None:
  if not job_data["REMOTE_GLOBAL"] and not job_data["VISA_SPONSOR"]:
    print("ℹ️ Tidak ada lowongan baru yang lolos seleksi hari ini.")
    return None

  if not GEMINI_API_KEY:
    print("⚠️ Warning: GEMINI_API_KEY tidak dikonfigurasi. Menggunakan raw fallback.")
    return format_jobs_raw_fallback(job_data)

  print("🤖 AI formatting direct job apply links with Gemini...")
  client = genai.Client(api_key=GEMINI_API_KEY)

  clean_input = {
      cat: [
          {"title": j["title"], "snippet": j["snippet"], "url": j["url"]}
          for j in job_data[cat]
      ]
      for cat in ["REMOTE_GLOBAL", "VISA_SPONSOR"]
  }

  prompt = f"""
You are an Executive Career Agent for Muchamat Riyan Khamdani.
Filter and synthesize these ATS job postings into an actionable Telegram card in Bahasa Indonesia.

CANDIDATE MASTER PROFILE:
{CANDIDATE_PROFILE}

FILTERED JOB DATA:
{json.dumps(clean_input, indent=2)}

STRICT INSTRUCTIONS:
1. Divide into 2 sections:
   - 🌐 <b>LOWONGAN REMOTE GLOBAL (TAP-TO-APPLY)</b>
   - ✈️ <b>LOWONGAN VISA SPONSOR / RELOKASI GLOBAL</b>
2. STRICT ELIMINATION:
   - Discard roles requiring US/EU citizenship, US-only remote, or local-only attendance without visa sponsorship.
   - Discard roles with < 75% match against Riyan's profile.
3. FOR EACH VALID ROLE:
   - Header: 🔥 <b>[Match Score]% MATCH — [Judul Posisi - Perusahaan]</b>
   - 📍 Lokasi & 💰 Estimasi Gaji wajar.
   - 📋 <i>Jawaban form ("Why Us?"):</i>
     Generate a 2-SENTENCE punchy, high-impact answer in English linking Riyan's tier-1 banking OpenShift/K8s resilience (99.9% uptime) and Terraform/Ansible DRC automation to the target company's mission.
     ENCLOSE THIS 2-SENTENCE ANSWER STRICTLY INSIDE <code>...</code> TAGS so Riyan can tap to copy it in 1 second on Telegram mobile.
   - 🔗 Apply: EXACT URL FROM DATA (Do not truncate or alter).
4. If a section has no qualifying jobs, write: "Belum ada lowongan dengan match tinggi hari ini."
5. OUTPUT FORMAT MUST USE VALID TELEGRAM HTML ONLY (<b>, <i>, <code>). DO NOT USE MARKDOWN (** or ```). Escape any < or > inside normal text.

OUTPUT FORMAT TEMPLATE:
💼 <b>DAILY JOB HUNTER DIGEST (ZERO-FRICTION)</b> 💼
====================================

🌐 <b>LOWONGAN REMOTE GLOBAL (TAP-TO-APPLY)</b>
- 🔥 <b>[Match Score]% MATCH — [Judul Posisi - Perusahaan]</b>
  📍 [Lokasi] | 💰 Est. Gaji: [Rentang Gaji]
  📋 <i>Jawaban form ("Why Us?"):</i>
  <code>[2-sentence high-impact pitch]</code>
  🔗 Apply: [URL]

✈️ <b>LOWONGAN VISA SPONSOR / RELOKASI GLOBAL</b>
- 🔥 <b>[Match Score]% MATCH — [Judul Posisi - Perusahaan]</b>
  📍 [Lokasi] | 💰 Est. Gaji: [Rentang Gaji]
  📋 <i>Jawaban form ("Why Us?"):</i>
  <code>[2-sentence high-impact pitch]</code>
  🔗 Apply: [URL]
"""

  models_to_try = [
      "gemini-2.5-flash",
      "gemini-2.5-flash-lite",
  ]

  for model_name in models_to_try:
    print(f"🔄 Mencoba model: {model_name}...")
    for attempt in range(1, retries + 1):
      try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        if response and response.text:
          return response.text
      except Exception as e:
        err_msg = str(e)
        print(f"⚠️ [{model_name}] attempt {attempt} failed: {err_msg[:200]}")

        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
          time.sleep(6 * attempt)
        elif "503" in err_msg or "UNAVAILABLE" in err_msg:
          time.sleep(4 * attempt)
        elif "404" in err_msg or "NOT_FOUND" in err_msg:
          break
        else:
          time.sleep(2 * attempt)

  print("⚠️ Semua model AI gagal/padat. Mengaktifkan raw text fallback...")
  return format_jobs_raw_fallback(job_data)


def send_telegram(message: str):
  if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ Error: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan.")
    return

  url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_BOT_TOKEN}/sendMessage"
  chunks = [message[i : i + 4000] for i in range(0, len(message), 4000)]

  for chunk in chunks:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": chunk,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
      res = requests.post(url, json=payload, timeout=10)
      if res.status_code != 200:
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

    for cat in ["REMOTE_GLOBAL", "VISA_SPONSOR"]:
      for item in job_data[cat]:
        seen_urls.add(item["hash"])
        seen_urls.add(item["clean_url"])
    save_seen_urls(seen_urls)
  else:
    print("⚠️ Gagal memproses lowongan.")


if __name__ == "__main__":
  main()
