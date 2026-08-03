import os
import json
import requests
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate

# 1. Credentials dari Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 2. Profil Lu Berdasarkan CV
CANDIDATE_PROFILE = """
Candidate Name: Muchamat Riyan Khamdani
Education: Bachelor of Applied Science in Internet Engineering Technology (UGM)
Current Role: Cloud Engineer / SRE
Tech Stack & Skills: 
- Cloud: AWS, GCP, Alibaba Cloud (ACA Certified), VMware vSphere/vCloud, NSX-T
- IaC & Automation: Terraform, Ansible, Python, Shell Scripting
- CI/CD & Containers: Docker, Jenkins, Bamboo
- Observability & DB: Grafana, PostgreSQL, MySQL (Tuning & HA)
- Infrastructure & Disaster Recovery: Zerto, DRC Automation, Networking (MikroTik)

Job Preferences:
1. FULLY REMOTE (Worldwide / APAC / Europe / US Timezones).
2. ONSITE / HYBRID in any region (Europe, Japan, SG, UAE, Australia, Canada, etc.) BUT MUST EXPLICITLY PROVIDE VISA SPONSORSHIP / RELOCATION.
"""

def search_jobs():
    search_tool = TavilySearchResults(max_results=8)
    
    # Query pencarian spesifik lowongan remote & visa sponsorship
    queries = [
        "site:relocate.me Cloud Engineer OR DevOps visa sponsorship",
        "site:greenhouse.io OR site:lever.co Cloud Engineer remote worldwide Terraform Ansible",
        "DevOps Cloud Engineer visa sponsorship Europe 2026",
        "Senior Cloud Engineer remote worldwide Terraform Grafana",
        "Alibaba Cloud AWS Engineer remote hiring"
    ]
    
    raw_results = []
    print("🔎 Searching for jobs matching Riyan's profile...")
    for q in queries:
        try:
            res = search_tool.invoke({"query": q})
            raw_results.extend(res)
        except Exception as e:
            print(f"Error searching for '{q}': {e}")
            
    return raw_results

def filter_and_format_jobs(raw_jobs):
    print("🤖 Agent analyzing jobs against CV profile...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    
    prompt_template = ChatPromptTemplate.from_template("""
    You are a professional Job Hunter AI Agent acting for Muchamat Riyan Khamdani.
    
    Candidate Profile:
    {profile}

    Raw Search Results:
    {raw_jobs}

    Task:
    1. Filter the listings to ONLY keep jobs that fit ANY of these criteria:
       - Criterion A: Fully Remote (Worldwide or flexible location).
       - Criterion B: Onsite/Hybrid ANYWHERE, but EXPLICITLY provides Visa Sponsorship or Relocation assistance.
    2. Ignore jobs requiring local work authorization/citizenship without sponsorship.
    3. Format the response for Telegram in Bahasa Indonesia.

    Expected Output Format per Job:
    🚀 **[Job Title]**
    🏢 **Company:** [Name]
    📍 **Location:** [Remote Worldwide / Onsite City + Visa Sponsored]
    🛠 **Stack Match:** [e.g. AWS, Terraform, Ansible, Grafana]
    🔗 **Link:** [URL]
    ---

    If no strong matches are found in this run, return "NO_MATCHES".
    """)

    chain = prompt_template | llm
    response = chain.invoke({
        "profile": CANDIDATE_PROFILE,
        "raw_jobs": json.dumps(raw_jobs)
    })
    
    return response.content

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram keys missing. Printing output to log:")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

if __name__ == "__main__":
    raw_data = search_jobs()
    formatted_report = filter_and_format_jobs(raw_data)
    
    if "NO_MATCHES" in formatted_report or not formatted_report.strip():
        print("No matches found today.")
    else:
        header = "⚡ **JOB HUNTER AGENT REPORT (For Riyan)** ⚡\n\n"
        send_telegram(header + formatted_report)
