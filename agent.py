import os
import json
import requests
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

# Credentials
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CANDIDATE_PROFILE = """
Candidate Name: Muchamat Riyan Khamdani
Current Role: Cloud Engineer / SRE / DevOps
Tech Stack: AWS, GCP, Alibaba Cloud, Terraform, Ansible, Docker, Kubernetes, Jenkins, Grafana, PostgreSQL.
Preferences: Remote Worldwide, OR Onsite with Visa Sponsorship.
"""

def search_tavily_direct(query):
    """Panggil Tavily API langsung via HTTP Request (Anti-Gagal)"""
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": 4,
        "search_depth": "basic"
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            results = response.json().get("results", [])
            # Ambil title, content, dan url aja biar ringkas
            return [{"title": r.get("title"), "url": r.get("url"), "content": r.get("content")} for r in results]
        else:
            print(f"Tavily Error ({response.status_code}): {response.text}")
            return []
    except Exception as e:
        print(f"Failed Tavily search for '{query}': {e}")
        return []

def search_all_jobs():
    queries = [
        "Cloud Engineer remote hiring worldwide 2026",
        "DevOps Engineer visa sponsorship Europe remote job",
        "Site Reliability Engineer remote worldwide Terraform",
        "site:greenhouse.io Cloud Engineer remote"
    ]
    
    all_results = []
    print("🔎 Searching real jobs from web...")
    for q in queries:
        results = search_tavily_direct(q)
        all_results.extend(results)
        
    print(f"✅ Found {len(all_results)} raw job articles/postings.")
    return all_results

def filter_and_format_jobs(raw_jobs):
    print("🤖 Agent analyzing REAL jobs using Groq Llama 3.3...")
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.1, api_key=GROQ_API_KEY)
    
    prompt_template = ChatPromptTemplate.from_template("""
    You are an expert Job Hunter AI Agent for Muchamat Riyan Khamdani.
    Candidate Profile: {profile}
    
    REAL Search Data from the Web:
    {raw_jobs}

    CRITICAL INSTRUCTION:
    1. Extract 3 to 5 ACTUAL job openings from the search data provided above.
    2. DO NOT MAKE UP OR HALLUCINATE ANY JOBS. ONLY use the URLs and Companies provided in the Raw Search Data.
    3. If a link isn't a job application, skip it.

    Format the final report in Bahasa Indonesia for Telegram like this:

    ⚡ **JOB HUNTER REPORT (Riyan)** ⚡

    🚀 **[Job Title]**
    🏢 **Perusahaan:** [Company Name]
    📍 **Lokasi/Tipe:** [Remote / City]
    🛠 **Summary:** [Brief job summary / required stack]
    🔗 **Link:** [Real URL from data]

    ---
    """)

    chain = prompt_template | llm
    response = chain.invoke({
        "profile": CANDIDATE_PROFILE,
        "raw_jobs": json.dumps(raw_jobs, indent=2)
    })
    
    return response.content

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    res = requests.post(url, json=payload)
    if res.status_code != 200:
        print(f"Failed to send Telegram message: {res.text}")
    else:
        print("🚀 Message successfully sent to Telegram!")

if __name__ == "__main__":
    raw_data = search_all_jobs()
    if not raw_data:
        print("No search results returned from Tavily. Check TAVILY_API_KEY.")
    else:
        formatted_report = filter_and_format_jobs(raw_data)
        send_telegram(formatted_report)
