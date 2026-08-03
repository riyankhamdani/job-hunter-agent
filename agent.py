import os
import json
import requests
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langchain_core.prompts import ChatPromptTemplate

# Credentials dari Environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CANDIDATE_PROFILE = """
Candidate Name: Muchamat Riyan Khamdani
Education: Bachelor of Applied Science in Internet Engineering Technology (UGM)
Current Role: Cloud Engineer / SRE
Tech Stack: AWS, GCP, Alibaba Cloud (ACA), Terraform, Ansible, Docker, Jenkins, Bamboo, Grafana, PostgreSQL, MySQL, VMware, Zerto.

Preferences:
1. FULLY REMOTE (Worldwide / APAC / Europe / US Timezones).
2. ONSITE / HYBRID BUT MUST EXPLICITLY PROVIDE VISA SPONSORSHIP / RELOCATION.
"""

def search_jobs():
    search_tool = TavilySearch(max_results=8)
    queries = [
        "site:relocate.me Cloud Engineer OR DevOps visa sponsorship",
        "site:greenhouse.io OR site:lever.co Cloud Engineer remote worldwide Terraform Ansible",
        "DevOps Cloud Engineer visa sponsorship Europe 2026",
        "Senior Cloud Engineer remote worldwide Terraform Grafana"
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
    print("🤖 Agent analyzing jobs using Groq Llama 3.3...")
    # Menggunakan model Llama 3.3 70B yang sangat pintar & gratis di Groq
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.1, api_key=GROQ_API_KEY)
    
    prompt_template = ChatPromptTemplate.from_template("""
    You are a professional Job Hunter AI Agent acting for Muchamat Riyan Khamdani.
    Candidate Profile: {profile}
    Raw Search Results: {raw_jobs}

    Task:
    1. Filter to ONLY keep jobs that fit:
       - Fully Remote (Worldwide or flexible)
       - OR Onsite/Hybrid WITH Visa Sponsorship / Relocation assistance.
    2. Format for Telegram in Bahasa Indonesia:
       🚀 **[Job Title]**
       🏢 **Company:** [Name]
       📍 **Location:** [Remote / City + Visa]
       🛠 **Stack Match:** [Key Techs]
       🔗 **Link:** [URL]
       ---
    If no strong matches found, return "NO_MATCHES".
    """)

    chain = prompt_template | llm
    response = chain.invoke({
        "profile": CANDIDATE_PROFILE,
        "raw_jobs": json.dumps(raw_jobs)
    })
    
    return response.content

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram keys missing. Output to log:\n", text)
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
