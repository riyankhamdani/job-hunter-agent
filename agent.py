import os
import requests
from langchain_groq import ChatGroq

# Credentials
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def search_tavily_direct(query):
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": 3,
        "search_depth": "basic"
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            results = response.json().get("results", [])
            return [{"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content", "")[:200]} for r in results]
        return []
    except Exception as e:
        print(f"Error Tavily: {e}")
        return []

def get_real_jobs():
    queries = [
        "Cloud Engineer remote hiring worldwide 2026",
        "DevOps Engineer visa sponsorship Europe job",
        "Site Reliability Engineer remote Terraform"
    ]
    
    all_results = []
    print("🔎 Searching real job postings from Tavily...")
    for q in queries:
        res = search_tavily_direct(q)
        all_results.extend(res)
    
    # Hapus duplikat berdasarkan URL
    unique_jobs = {item['url']: item for item in all_results}.values()
    return list(unique_jobs)

def filter_with_groq(jobs):
    print("🤖 Agent filtering real jobs...")
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.1, api_key=GROQ_API_KEY)
    
    valid_jobs = []
    for job in jobs[:7]: # Cek max 7 lowongan teratas
        prompt = f"""
        Analyze if this web search result is an ACTUAL Job Opening/Career Opportunity for Cloud/DevOps/SRE Engineer.
        Title: {job['title']}
        Snippet: {job['snippet']}
        
        Answer ONLY with "YES" or "NO". Do not explain anything else.
        """
        try:
            res = llm.invoke(prompt).content.strip().upper()
            if "YES" in res:
                valid_jobs.append(job)
        except Exception as e:
            print(f"Groq filter error: {e}")
            valid_jobs.append(job) # Tetep masukin kalo Groq error
            
    return valid_jobs if valid_jobs else jobs[:4] # Fallback pake 4 job pertama kalo AI ngambek

def send_telegram(jobs):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing!")
        return

    message = "⚡ JOB HUNTER REPORT FOR RIYAN ⚡\n"
    message += "=============================\n\n"
    
    for idx, j in enumerate(jobs, 1):
        message += f"{idx}. {j['title']}\n"
        message += f"🔗 Link: {j['url']}\n"
        message += "-----------------------------\n\n"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }
    
    res = requests.post(url, json=payload)
    if res.status_code == 200:
        print("🚀 Message successfully delivered to Telegram!")
    else:
        print(f"❌ Telegram Failed: {res.text}")

if __name__ == "__main__":
    raw_jobs = get_real_jobs()
    if raw_jobs:
        filtered_jobs = filter_with_groq(raw_jobs)
        send_telegram(filtered_jobs)
    else:
        print("No jobs found from Tavily.")
