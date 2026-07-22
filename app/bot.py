import os
import html
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from typing import List, Optional

from .models import Job
from .storage import load_jobs, save_jobs, DB_FILE
from .scraper import scrape_all
from .agent import load_profile, filter_jobs, enrich_and_score

logger = logging.getLogger(__name__)


import sqlite3
from typing import Tuple

VALID_TOPICS = {
    "pune", "bangalore", "mumbai", "hyderabad", "chennai", "delhi_ncr",
    "india_remote", "apac_remote", "global_remote", "apac_jobs", "visa_sponsored",
    "data_analytics", "python_developer", "data_scientist", "ml_ai", "data_engineering"
}

TOPIC_FRIENDLY_NAMES = {
    "pune": "🏢 Pune Jobs",
    "bangalore": "🏢 Bangalore Jobs",
    "mumbai": "🏢 Mumbai Jobs",
    "hyderabad": "🏢 Hyderabad Jobs",
    "chennai": "🏢 Chennai Jobs",
    "delhi_ncr": "🏢 Delhi-NCR Jobs",
    "india_remote": "🇮🇳 India Remote",
    "apac_remote": "🌏 APAC Remote",
    "global_remote": "🌍 Global Remote",
    "apac_jobs": "🌏 APAC Jobs",
    "visa_sponsored": "🛂 Visa Sponsored",
    "data_analytics": "📊 Data Analytics",
    "python_developer": "🐍 Python Developer",
    "data_scientist": "🧪 Data Scientist (Jr)",
    "ml_ai": "🤖 ML / AI (Jr)",
    "data_engineering": "💾 Data Engineering"
}


def get_linked_thread_id(topic: str) -> int | None:
    """Get the thread ID linked to a topic from SQLite DB."""
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT thread_id FROM topic_threads WHERE topic = ?", (topic.lower().strip(),))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def link_topic_to_thread(topic: str, thread_id: int, user_info: str) -> Tuple[bool, Optional[int]]:
    """Link a topic to a thread ID. Returns: (success, old_thread_id)."""
    topic_clean = topic.lower().strip()
    old_thread = get_linked_thread_id(topic_clean)
    
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        now_str = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO topic_threads (topic, thread_id, linked_by, linked_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(topic) DO UPDATE SET
                thread_id=excluded.thread_id,
                linked_by=excluded.linked_by,
                linked_at=excluded.linked_at
        """, (topic_clean, thread_id, user_info, now_str))
        conn.commit()
        return True, old_thread
    finally:
        conn.close()


def unlink_topic(topic: str) -> Optional[int]:
    """Unlink a topic. Returns the unlinked thread ID if existed."""
    topic_clean = topic.lower().strip()
    old_thread = get_linked_thread_id(topic_clean)
    if old_thread is None:
        return None
        
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM topic_threads WHERE topic = ?", (topic_clean,))
        conn.commit()
        return old_thread
    finally:
        conn.close()


def get_all_linked_topics() -> List[dict]:
    """Get all topic mappings from DB."""
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT topic, thread_id, linked_by, linked_at FROM topic_threads")
        rows = cursor.fetchall()
        return [
            {
                "topic": r[0],
                "thread_id": r[1],
                "linked_by": r[2],
                "linked_at": r[3]
            } for r in rows
        ]
    finally:
        conn.close()


def clean_description(desc_html: str) -> str:
    """Strip all HTML tags and normalize spaces using BeautifulSoup."""
    if not desc_html:
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(desc_html, "html.parser")
        text = soup.get_text(separator=" ")
        return " ".join(text.split())
    except Exception:
        import re
        clean = re.sub(r'<[^>]+>', '', desc_html)
        return " ".join(clean.split())


def classify_job_topics(job: Job) -> List[str]:
    """Classify a job into highly targeted geographical and role-based topics."""
    topics = []
    title = (job.title or "").lower()
    desc = (job.description or "").lower()
    loc = (job.location or "").lower()
    
    # Geographies
    if "pune" in loc or "pune" in title:
        topics.append("pune")
    if any(x in loc or x in title for x in ["bangalore", "bengaluru", "blr", "bang"]):
        topics.append("bangalore")
    if "mumbai" in loc or "mumbai" in title:
        topics.append("mumbai")
    if "hyderabad" in loc or "hyderabad" in title:
        topics.append("hyderabad")
    if "chennai" in loc or "chennai" in title:
        topics.append("chennai")
    if any(x in loc or x in title for x in ["delhi", "ncr", "noida", "gurgaon", "gurugram"]):
        topics.append("delhi_ncr")
        
    is_remote = "remote" in loc or "remote" in title
    if is_remote:
        if "india" in loc or "india" in title or "in" in loc:
            topics.append("india_remote")
        elif any(x in loc or x in title for x in ["apac", "asia", "singapore", "sg", "philippines", "ph", "malaysia", "vietnam"]):
            topics.append("apac_remote")
        else:
            if not any(x in loc for x in ["germany", "de", "us", "uk", "canada", "ca", "europe", "eu"]):
                topics.append("global_remote")
    else:
        if any(x in loc for x in ["singapore", "malaysia", "philippines", "vietnam", "thailand", "indonesia"]):
            topics.append("apac_jobs")
            
    if "visa" in desc or "sponsorship" in desc or getattr(job, "visa_sponsorship", False):
        if not any(x in desc for x in ["no visa", "cannot sponsor", "do not sponsor"]):
            topics.append("visa_sponsored")

    # Roles
    analytics_keywords = ["analytics", "analyst", "bi dev", "bi developer", "power bi", "tableau", "business intelligence"]
    if any(x in title for x in analytics_keywords):
        topics.append("data_analytics")
        
    if "python" in title and "developer" in title or "python engineer" in title:
        topics.append("python_developer")
        
    if "data scientist" in title or "data science" in title:
        if any(x in title or x in desc for x in ["junior", "intern", "associate", "entry level", "grad"]):
            topics.append("data_scientist")
            
    if any(x in title for x in ["machine learning", "ml ", "ml engineer", "artificial intelligence", "ai engineer", "deep learning"]):
        if any(x in title or x in desc for x in ["junior", "intern", "associate", "entry level", "grad"]):
            topics.append("ml_ai")
            
    if "data engineer" in title or "data engineering" in title or "pipeline engineer" in title:
        topics.append("data_engineering")
        
    return topics


def get_topic_thread_id(topic: str) -> int | None:
    """Resolve thread ID for a specific classified topic (looks up SQLite first, then env)."""
    # 1. Check SQLite mappings
    thread_id = get_linked_thread_id(topic)
    if thread_id is not None:
        return thread_id
        
    # 2. Check environment fallback
    env_name = f"TELEGRAM_THREAD_{topic.upper()}"
    val = os.environ.get(env_name, "").strip()
    return int(val) if val.isdigit() else None


def filter_jobs_by_key(jobs: List[Job], key: str) -> List[Job]:
    """Filter jobs by pre-defined location categories."""
    out = []
    k = key.lower()
    for j in jobs:
        loc = (j.location or "").lower()
        title = (j.title or "").lower()
        
        if k == "pune" and ("pune" in loc or "pune" in title):
            out.append(j)
        elif k == "bangalore" and any(x in loc or x in title for x in ["bangalore", "bengaluru", "blr", "bang"]):
            out.append(j)
        elif k == "mumbai" and ("mumbai" in loc or "mumbai" in title):
            out.append(j)
        elif k == "india_remote" and ("remote" in loc or "remote" in title) and ("india" in loc or "india" in title or "in" in loc):
            out.append(j)
        elif k == "global_remote" and ("remote" in loc or "remote" in title) and not any(x in loc for x in ["germany", "de", "us", "uk", "canada", "ca", "europe", "eu"]):
            out.append(j)
        elif k == "all":
            out.append(j)
    return out


def make_link_menu_keyboard(thread_id: int) -> dict:
    """Generate inline buttons for all valid topics to map to the current thread."""
    buttons = []
    sorted_topics = sorted(list(VALID_TOPICS))
    
    row = []
    for topic in sorted_topics:
        friendly = TOPIC_FRIENDLY_NAMES.get(topic, topic)
        
        linked_tid = get_linked_thread_id(topic)
        button_text = friendly
        if linked_tid is not None:
            if linked_tid == thread_id:
                button_text = f"✅ {friendly}"
            else:
                button_text = f"🔄 {friendly} (T:{linked_tid})"
                
        row.append({"text": button_text, "callback_data": f"lnk:{topic}:{thread_id}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
            
    if row:
        buttons.append(row)
        
    buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_link"}])
    return {"inline_keyboard": buttons}


def make_main_menu_keyboard() -> dict:
    """Generate main interactive inline keyboard options."""
    return {
        "inline_keyboard": [
            [
                {"text": "🇮🇳 India Remote", "callback_data": "f:india_remote:0"},
                {"text": "🌍 Global Remote", "callback_data": "f:global_remote:0"}
            ],
            [
                {"text": "🏢 Pune Jobs", "callback_data": "f:pune:0"},
                {"text": "🏢 Bangalore Jobs", "callback_data": "f:bangalore:0"}
            ],
            [
                {"text": "🏢 Mumbai Jobs", "callback_data": "f:mumbai:0"},
                {"text": "🔄 Refresh Scrapers", "callback_data": "trigger_refresh"}
            ]
        ]
    }


def make_pagination_keyboard(query: str, page: int, total_pages: int, is_filter: bool = False) -> dict:
    """Generate Prev/Next/Menu inline navigation buttons."""
    buttons = []
    row = []
    query_slug = query[:20]
    
    if page > 0:
        prev_data = f"f:{query_slug}:{page-1}" if is_filter else f"p:{page-1}:{query_slug}"
        row.append({"text": "⬅️ Prev", "callback_data": prev_data})
        
    if page < total_pages - 1:
        next_data = f"f:{query_slug}:{page+1}" if is_filter else f"p:{page+1}:{query_slug}"
        row.append({"text": "Next ➡️", "callback_data": next_data})
        
    if row:
        buttons.append(row)
        
    buttons.append([{"text": "📱 Main Menu", "callback_data": "menu"}])
    return {"inline_keyboard": buttons}


def format_posted_ago(job_date) -> str:
    """Calculate the human-readable time elapsed since job posting."""
    if not job_date:
        return "recently"
    if isinstance(job_date, str):
        try:
            dt = datetime.fromisoformat(job_date.replace("Z", "+00:00"))
        except Exception:
            return "recently"
    else:
        dt = job_date
        
    delta = datetime.now(dt.tzinfo or timezone.utc) - dt
    if delta.days <= 0:
        return "today"
    elif delta.days == 1:
        return "1 day ago"
    else:
        return f"{delta.days} days ago"


def format_jobs_page(jobs: List[Job], query: str, page: int, per_page: int = 5, title_prefix: str = "Search") -> str:
    """Format a clean, concise page of jobs for Telegram message view."""
    total = len(jobs)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    start = page * per_page
    end = min(start + per_page, total)
    
    header = f"🔍 <b>{title_prefix} for: \"{html.escape(query)}\"</b> (Page {page + 1} of {total_pages})\n\n"
    
    lines = [header]
    if total == 0:
        lines.append("<i>No matching jobs found.</i>")
    else:
        for idx, j in enumerate(jobs[start:end], start=start+1):
            title = html.escape(j.title or "Unknown Role")
            company = html.escape(j.company or "Unknown Company")
            location = html.escape(j.location or "Remote")
            ago = format_posted_ago(j.date)
            apply_url = j.url or ""
            
            line = (
                f"{idx}. 💼 <b>{title}</b>\n"
                f"   🏢 {company} | 📍 {location}\n"
                f"   ⏳ {ago} | 🔗 <a href='{apply_url}'>Apply</a>\n\n"
            )
            lines.append(line)
            
    return "".join(lines)


async def notify_telegram(jobs: List[Job]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not chat_id:
        return
        
    filter_mode = os.environ.get("TELEGRAM_FILTER_MODE", "all").strip().lower()
    
    if filter_mode == "filtered":
        agent_prof = load_profile()
        enriched_jobs = []
        for j in jobs:
            try:
                enriched_jobs.append(enrich_and_score(j, agent_prof))
            except Exception:
                enriched_jobs.append(j)
        jobs = filter_jobs(enriched_jobs, agent_prof)
        
    if not jobs:
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        for j in jobs:
            title = j.title or "Unknown Role"
            company = j.company or "Unknown Company"
            location = j.location or "Remote/Global"
            apply_url = j.url or ""
            
            title = html.escape(title)
            company = html.escape(company)
            location = html.escape(location)
            
            desc_snippet = ""
            if j.description:
                raw_desc = clean_description(j.description)
                if len(raw_desc) > 200:
                    desc_snippet = f"\n📝 <b>Description:</b> {html.escape(raw_desc[:200])}...\n"
                else:
                    desc_snippet = f"\n📝 <b>Description:</b> {html.escape(raw_desc)}\n"
                    
            text = (
                f"📢 <b>New Job Alert</b>\n\n"
                f"💼 <b>Role:</b> {title}\n"
                f"🏢 <b>Company:</b> {company}\n"
                f"📍 <b>Location:</b> {location}\n"
            )
            if getattr(j, "match_score", None) is not None:
                text += f"🎯 <b>Match Score:</b> {j.match_score}%\n"
            if getattr(j, "yoe_min", None) is not None or getattr(j, "yoe_max", None) is not None:
                y_min = j.yoe_min if j.yoe_min is not None else 0
                y_max = j.yoe_max if j.yoe_max is not None else "+"
                text += f"⏳ <b>Experience:</b> {y_min}-{y_max} YOE\n"
            if j.source:
                text += f"🏷️ <b>Source:</b> {j.source}\n"
                
            text += desc_snippet
            text += f"\n🔗 <a href='{apply_url}'>Apply here</a>"
            
            # Classify job topics
            matched_topics = classify_job_topics(j)
            
            # If no topics matched, send to main channel ID with no thread
            if not matched_topics:
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                }
                try:
                    await client.post(url, json=payload)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending Telegram notification: {e}")
            else:
                # Send to each matched topic thread (avoiding duplicate thread sends)
                sent_threads = set()
                for topic in matched_topics:
                    thread_id = get_topic_thread_id(topic)
                    if thread_id is not None and thread_id not in sent_threads:
                        payload = {
                            "chat_id": chat_id,
                            "text": text,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True,
                            "message_thread_id": thread_id
                        }
                        try:
                            await client.post(url, json=payload)
                            sent_threads.add(thread_id)
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.error(f"Error sending Telegram notification to thread {thread_id} for topic {topic}: {e}")


async def run_background_refresh() -> None:
    """Trigger standard background scrape and notification workflow."""
    existing_jobs = load_jobs()
    existing_urls = {j.url for j in existing_jobs if j.url}
    
    enable_headless = os.getenv("ENABLE_HEADLESS", "0") == "1"
    jobs = await scrape_all(days=3, query="data analyst", enable_headless=enable_headless, mode="all")
    save_jobs(jobs)
    
    new_jobs = [j for j in jobs if j.url and j.url not in existing_urls]
    if new_jobs:
        await notify_telegram(new_jobs)


async def handle_tg_webhook(update: dict, background_tasks) -> dict:
    """Process bot commands and callback query interactions."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return {"ok": False, "error": "Bot token not configured"}
        
    callback_query = update.get("callback_query")
    if callback_query:
        callback_id = callback_query.get("id")
        data = (callback_query.get("data") or "").strip()
        message = callback_query.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        thread_id = message.get("message_thread_id")
        
        if not chat_id or not message_id:
            return {"ok": True}
            
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={"callback_query_id": callback_id}
            )
            
        async def edit_reply(reply_text: str, reply_markup: dict = None):
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": reply_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            url = f"https://api.telegram.org/bot{token}/editMessageText"
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload)
                
        if data == "menu":
            menu_msg = (
                "🤖 <b>Job Search Menu</b>\n\n"
                "Select a pre-filtered location category or trigger a fresh scrape using the options below."
            )
            await edit_reply(menu_msg, make_main_menu_keyboard())
            
        elif data == "trigger_refresh":
            await edit_reply("🔄 <b>Scraper Triggered!</b> Running job scrapers in the background. Fresh matches will be posted here soon...", make_main_menu_keyboard())
            background_tasks.add_task(run_background_refresh)
            
        elif data.startswith("f:"):
            parts = data.split(":")
            if len(parts) == 3:
                _, filter_key, page_str = parts
                page = int(page_str)
                all_jobs = load_jobs()
                matched = filter_jobs_by_key(all_jobs, filter_key)
                matched.sort(key=lambda x: getattr(x, "date", datetime.utcnow()) or datetime.utcnow(), reverse=True)
                
                total_pages = (len(matched) + 4) // 5 if matched else 1
                text = format_jobs_page(matched, filter_key, page, per_page=5, title_prefix="Category Filter")
                keyboard = make_pagination_keyboard(filter_key, page, total_pages, is_filter=True)
                await edit_reply(text, keyboard)
                
        elif data.startswith("p:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                _, page_str, query = parts
                page = int(page_str)
                all_jobs = load_jobs()
                matched = []
                for j in all_jobs:
                    title = j.title or ""
                    company = j.company or ""
                    description = j.description or ""
                    q_lower = query.lower()
                    if q_lower in title.lower() or q_lower in company.lower() or q_lower in description.lower():
                        matched.append(j)
                        
                matched.sort(key=lambda x: getattr(x, "date", datetime.utcnow()) or datetime.utcnow(), reverse=True)
                total_pages = (len(matched) + 4) // 5 if matched else 1
                text = format_jobs_page(matched, query, page, per_page=5, title_prefix="Search Results")
                keyboard = make_pagination_keyboard(query, page, total_pages, is_filter=False)
                await edit_reply(text, keyboard)
                
        elif data.startswith("lnk:"):
            parts = data.split(":")
            if len(parts) == 3:
                _, topic, target_thread_str = parts
                target_thread_id = int(target_thread_str)
                user_name = callback_query.get("from", {}).get("first_name", "User")
                
                success, old_thread = link_topic_to_thread(topic, target_thread_id, user_name)
                topic_friendly = TOPIC_FRIENDLY_NAMES.get(topic, topic)
                
                if old_thread is not None and old_thread != target_thread_id:
                    chat_stripped = str(chat_id).replace("-100", "")
                    new_thread_link = f"https://t.me/c/{chat_stripped}/{target_thread_id}"
                    
                    payload_old = {
                        "chat_id": chat_id,
                        "text": f"📢 Topic <b>{topic_friendly}</b> has been unlinked from this thread and linked to the <a href='{new_thread_link}'>new thread</a> by {user_name}!",
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                        "message_thread_id": old_thread
                    }
                    async with httpx.AsyncClient() as client:
                        await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload_old)
                        
                await edit_reply(f"✅ Linked topic <b>{topic_friendly}</b> to this thread!")
                
        elif data == "cancel_link":
            await edit_reply("❌ Topic linking cancelled.")
                
        return {"ok": True}

    message = update.get("message")
    if not message:
        return {"ok": True}
        
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    thread_id = message.get("message_thread_id")
    text = (message.get("text") or "").strip()
    
    if not chat_id or not text:
        return {"ok": True}
        
    async def send_reply(reply_text: str, reply_markup: dict = None):
        payload = {
            "chat_id": chat_id,
            "text": reply_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if thread_id is not None:
            payload["message_thread_id"] = thread_id
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)

    user_name = message.get("from", {}).get("first_name", "User")
    
    async def send_to_thread(target_thread_id: int, text_content: str):
        payload = {
            "chat_id": chat_id,
            "text": text_content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "message_thread_id": target_thread_id
        }
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)

    if text.startswith("/start") or text.startswith("/help") or text == "/menu":
        menu_msg = (
            "🤖 <b>Welcome to Job Search Assistant Bot!</b>\n\n"
            "Use the interactive menu below to select jobs by category, or use the text commands:\n\n"
            "🔍 <code>/fetch &lt;keyword&gt;</code> - Search matching jobs\n"
            "🔄 <code>/refresh</code> - Trigger background scraping\n"
            "🔗 <code>/link &lt;topic&gt;</code> - Link this thread to a topic\n"
            "❌ <code>/unlink &lt;topic&gt;</code> - Unlink a topic\n"
            "📊 <code>/status</code> - View topic mappings"
        )
        await send_reply(menu_msg, make_main_menu_keyboard())
        
    elif text.startswith("/link"):
        topic = text[5:].strip().lower()
        if not topic:
            if thread_id is None:
                await send_reply("⚠️ Please run this command inside a specific topic thread to link it.")
                return {"ok": True}
            menu_msg = "🔗 <b>Select a topic to link to this thread:</b>"
            await send_reply(menu_msg, make_link_menu_keyboard(thread_id))
            return {"ok": True}
            
        if topic not in VALID_TOPICS:
            valid_list = ", ".join(sorted(list(VALID_TOPICS)))
            await send_reply(f"❌ Invalid topic. Valid topics are:\n<code>{valid_list}</code>")
            return {"ok": True}
            
        if thread_id is None:
            await send_reply("⚠️ Please run this command inside a specific topic thread to link it.")
            return {"ok": True}
            
        old_thread = get_linked_thread_id(topic)
        topic_friendly = TOPIC_FRIENDLY_NAMES.get(topic, topic)
        if old_thread == thread_id:
            await send_reply(f"✅ Topic <b>{topic_friendly}</b> is already linked to this thread.")
        elif old_thread is not None:
            # Re-link automatically with notify redirection
            unlink_topic(topic)
            link_topic_to_thread(topic, thread_id, user_name)
            
            chat_stripped = str(chat_id).replace("-100", "")
            new_thread_link = f"https://t.me/c/{chat_stripped}/{thread_id}"
            
            await send_to_thread(
                old_thread,
                f"📢 Topic <b>{topic_friendly}</b> has been unlinked from this thread and linked to the <a href='{new_thread_link}'>new thread</a> by {user_name}!"
            )
            await send_reply(f"✅ Re-linked topic <b>{topic_friendly}</b> to this thread! (Moved from old thread <code>{old_thread}</code>).")
        else:
            link_topic_to_thread(topic, thread_id, user_name)
            await send_reply(f"✅ Linked topic <b>{topic_friendly}</b> to this thread!")

    elif text.startswith("/unlink_and_link"):
        topic = text[16:].strip().lower()
        if not topic or topic not in VALID_TOPICS or thread_id is None:
            await send_reply("⚠️ Invalid request. Usage: <code>/unlink_and_link &lt;topic&gt;</code> inside a topic thread.")
            return {"ok": True}
            
        old_thread = unlink_topic(topic)
        link_topic_to_thread(topic, thread_id, user_name)
        
        chat_stripped = str(chat_id).replace("-100", "")
        new_thread_link = f"https://t.me/c/{chat_stripped}/{thread_id}"
        topic_friendly = TOPIC_FRIENDLY_NAMES.get(topic, topic)
        
        if old_thread is not None:
            await send_to_thread(
                old_thread,
                f"📢 Topic <b>{topic_friendly}</b> has been unlinked from this thread and linked to the <a href='{new_thread_link}'>new thread</a> by {user_name}!"
            )
            
        await send_reply(f"✅ Re-linked topic <b>{topic_friendly}</b> to this thread! (Unlinked from old thread <code>{old_thread}</code>).")

    elif text.startswith("/unlink"):
        topic = text[7:].strip().lower()
        if not topic:
            await send_reply("⚠️ Usage: <code>/unlink &lt;topic&gt;</code>")
            return {"ok": True}
            
        old_thread = unlink_topic(topic)
        topic_friendly = TOPIC_FRIENDLY_NAMES.get(topic, topic)
        if old_thread is not None:
            await send_reply(f"✅ Unlinked topic <b>{topic_friendly}</b> from thread <code>{old_thread}</code>.")
        else:
            await send_reply(f"ℹ️ Topic <b>{topic_friendly}</b> was not linked.")

    elif text.startswith("/status") or text.startswith("/topics"):
        mappings = get_all_linked_topics()
        if not mappings:
            await send_reply("📊 <b>No topics are currently linked to any threads.</b>\nUse <code>/link</code> inside a thread to map it.")
            return {"ok": True}
            
        chat_stripped = str(chat_id).replace("-100", "")
        lines = ["📊 <b>Current Topic Mappings:</b>\n"]
        for m in mappings:
            t = m["topic"]
            friendly = TOPIC_FRIENDLY_NAMES.get(t, t)
            tid = m["thread_id"]
            user = m["linked_by"]
            thread_link = f"https://t.me/c/{chat_stripped}/{tid}"
            lines.append(f"• <b>{friendly}</b>: <a href='{thread_link}'>Thread {tid}</a> (linked by {user})")
            
        await send_reply("\n".join(lines))

    elif text.startswith("/fetch") or text.startswith("/search"):
        cmd_len = 7 if text.startswith("/search") else 6
        query = text[cmd_len:].strip()
        if not query:
            menu_msg = (
                "🤖 <b>Job Search Menu</b>\n\n"
                "Select a pre-filtered location category or trigger a fresh scrape using the options below."
            )
            await send_reply(menu_msg, make_main_menu_keyboard())
            return {"ok": True}
            
        await send_reply(f"🔍 Searching database for: <b>{html.escape(query)}</b>...")
        
        all_jobs = load_jobs()
        matched = []
        for j in all_jobs:
            title = j.title or ""
            company = j.company or ""
            description = j.description or ""
            q_lower = query.lower()
            if q_lower in title.lower() or q_lower in company.lower() or q_lower in description.lower():
                matched.append(j)
                
        matched.sort(key=lambda x: getattr(x, "date", datetime.utcnow()) or datetime.utcnow(), reverse=True)
        total_pages = (len(matched) + 4) // 5 if matched else 1
        text_resp = format_jobs_page(matched, query, 0, per_page=5, title_prefix="Search Results")
        keyboard = make_pagination_keyboard(query, 0, total_pages, is_filter=False)
        await send_reply(text_resp, keyboard)
        
    elif text.startswith("/refresh"):
        await send_reply("🔄 <b>Scraper Triggered!</b> Running job scrapers in the background. Fresh matches will be posted here soon...")
        background_tasks.add_task(run_background_refresh)
        
    return {"ok": True}


async def keep_awake_loop() -> None:
    """Ping ourselves every 10 minutes to stay awake on Render free tier."""
    host = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    if not host:
        host = "https://job-search-api-w042.onrender.com"
        
    logging.info(f"Starting keep-awake ping loop targeting: {host}")
    await asyncio.sleep(60)
    
    while True:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{host}/health")
                logging.info(f"Keep-awake self-ping: HTTP {res.status_code}")
        except Exception as e:
            logging.error(f"Keep-awake ping failed: {e}")
            
        await asyncio.sleep(600)
