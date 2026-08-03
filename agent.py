
import os
import json
import requests
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langchain_core.prompts import ChatPromptTemplate

# Credentials
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CANDIDATE_PROFILE = """
Candidate Name: Muchamat Riyan Khamdani
Education: Bachelor of Applied Science in Internet Engineering Technology (UGM)
Current Role: Cloud Engineer / SRE / DevOps
Tech Stack: AWS, GCP, Alibaba Cloud, Terraform, Ansible, Docker, Kubernetes, Jenkins, Bamboo, Grafana, PostgreSQL, MySQL.
Target Roles: Cloud Engineer, DevOps Engineer, Site Reliability Engineer (SRE), Infrastructure Engineer.
"""

def search_jobs():
    search_tool = TavilySearch(max_results=5)
    # Query dibuat lebih broad & modern
    queries = [
        "Cloud Engineer remote job hiring worldwide",
        "DevOps Engineer visa sponsorship Europe remote",
        "Site Reliability Engineer remote worldwide Terraform",
        "Senior Cloud Engineer remote hiring 2026"
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
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.2, api_key=GROQ_API_KEY)
    
    prompt_template = ChatPromptTemplate.from_template("""
    You are a helpful Career Assistant for Muchamat Riyan Khamdani.
    Candidate Profile: {profile}
    Raw Search Data: {raw_jobs}

    Task:
    Pick the TOP 3 to 5 most relevant Cloud/DevOps/SRE jobs from the search data.
    Even if a job isn't 100% explicit about remote/visa, as long as it matches his Cloud/DevOps stack, include it.

    Format the response in Bahasa Indonesia cleanly for Telegram (Use HTML tags or clean Markdown):

    ⚡ **JOB HUNTER REPORT (Riyan)** ⚡

    🚀 **[Job Title]**
    🏢 **Perusahaan:** [Company Name]
    📍 **Lokasi/Tipe:** [Remote / Location / Onsite]
    🛠 **Tech Stack:** [Matching Tech Stack]
    🔗 **Link:** [Direct URL]
    
    ---

    Do NOT return "NO_MATCHES". Always summarize the best opportunities found in the raw data.
    """)

    chain = prompt_template | llm
    response = chain.invoke({
        "profile": CANDIDATE_PROFILE,
        "raw_jobs": json.dumps(raw_jobs)
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
        print(f"Failed to send message via Telegram: {res.text}")
    else:
        print("Message successfully sent to Telegram!")

if __name__ == "__main__":
    raw_data = search_jobs()
    formatted_report = filter_and_format_jobs(raw_data)
    send_telegram(formatted_report)
