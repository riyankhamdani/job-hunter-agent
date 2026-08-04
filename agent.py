import os
import sys
import requests
from datetime import datetime
from langchain_groq import ChatGroq

# Credentials
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CANDIDATE_PROFILE = """
Candidate Name: Muchamat Riyan Khamdani
Education: Bachelor of Applied Science in Internet Engineering Technology (UGM)
Current Role: Cloud Engineer at Izeno (Prev: L2 Cloud Engineer at Datacomm Diangraha)
Tech Stack: AWS, GCP, Alibaba Cloud (ACA Certified), Terraform, Ansible, Docker, Kubernetes, Jenkins, Bamboo, Grafana, PostgreSQL, MySQL, VMware vSphere, NSX-T, Zerto.
Target Roles: Cloud Engineer, DevOps Engineer, Site Reliability Engineer (SRE), Infrastructure Engineer.
Preferences: Fully Remote Worldwide, OR Onsite with Visa Sponsorship/Relocation in Stable Countries.
"""

def search_tavily(query, domains=None):
    if not TAVILY_API_KEY:
        print("⚠️ Warning: TAVILY_API_KEY tidak ditemukan.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "topic": "general",
        "days": 1,                   # DIKUNCI 1 HARI (24 JAM TERAKHIR) BIAR GAK BASI!
        "max_results": 7,
        "search_depth": "advanced"
    }

    if domains:
        payload["include_domains"] = domains

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            results = response.json().get("results", [])
            valid_jobs = []

            # Validasi Domain ATS Direct & Link LinkedIn Spesifik
            allowed_domains = [
                "greenhouse.io", "jobs.lever.co", "apply.workable.com", 
                "jobs.smartrecruiters.com", "ashbyhq.com", "linkedin.com/jobs/view"
            ]

            for r in results:
                link = r.get("url", "")
                is_direct_job = any(domain in link for domain in allowed_domains)
                
                if is_direct_job:
                    valid_jobs.append({
                        "title": r.get("title", "Job Posting"),
                        "url": link,
                        "snippet": r.get("content", "")[:300]
                    })
            
            return valid_jobs[:3]
        return []
    except Exception as e:
        print(f"❌ Error searching '{query}': {e}")
        return []

def get_job_postings():
    today_str = datetime.now().strftime("%B %Y")
    
    # Domain ATS resmi untuk nembak link pendaftaran langsung
    ats_domains = [
        "boards.greenhouse.io", "job-boards.greenhouse.io", 
        "jobs.lever.co", "apply.workable.com", "ashbyhq.com"
    ]
    
    queries = {
        "REMOTE_GLOBAL": {
            "query": f"DevOps OR Cloud Engineer Remote Worldwide Anywhere {today_str}",
            "domains": ats_domains
        },
        "VISA_SPONSOR": {
            "query": f"DevOps OR Cloud Engineer visa sponsorship relocation Europe Switzerland Netherlands Sweden {today_str}",
            "domains": ["linkedin.com", "jobs.lever.co", "boards.greenhouse.io"]
        }
    }
    
    job_data = {}
    print(f"🔎 Searching direct job apply links (Past 24 Hours) for {today_str}...")
    for category, config in queries.items():
        job_data[category] = search_tavily(config["query"], config["domains"])
        
    return job_data

def summarize_with_groq(job_data):
    if not GROQ_API_KEY:
        return "❌ Error: GROQ_API_KEY tidak dikonfigurasi."

    print("🤖 AI formatting direct job apply links...")
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.1, api_key=GROQ_API_KEY)
    
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
    3. For each job, output ONLY:
       - Bold Job Title & Company Name
       - 1 short sentence summarizing key requirements/tech stack matching Riyan
       - The EXACT direct application link provided in the raw data.
    4. ABSOLUTE RULE FOR URL: Copy the exact full "url" string provided in the raw data without altering it.

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
        report = llm.invoke(prompt).content
        return report
    except Exception as e:
        print(f"Summarizer Error: {e}")
        return "Gagal membuat daftar lowongan kerja hari ini."

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials missing!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    
    res = requests.post(url, json=payload, timeout=10)
    if res.status_code == 200:
        print("🚀 Direct Job Digest successfully sent to Telegram!")
    else:
        print(f"❌ Telegram Send Failed: {res.text}")

if __name__ == "__main__":
    raw_jobs = get_job_postings()
    summary = summarize_with_groq(raw_jobs)
    send_telegram(summary)
