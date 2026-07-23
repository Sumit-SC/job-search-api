import os
import html
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from typing import List, Optional

from .models import Job
from .storage import (
    load_jobs, save_jobs, DB_FILE, save_user_profile, get_user_profile,
    get_linked_thread_id, link_topic_to_thread, unlink_topic, get_all_linked_topics
)
from .scraper import scrape_all
from .agent import load_profile, filter_jobs, enrich_and_score

logger = logging.getLogger(__name__)


from typing import Tuple

VALID_TOPICS = {
    "pune", "bangalore", "mumbai", "hyderabad", "chennai", "delhi_ncr", "india",
    "india_remote", "apac_remote", "global_remote", "worldwide_remote", "apac_jobs", "eu_jobs", "arab_jobs",
    "visa_sponsored", "data_analytics", "python_developer", "data_scientist", "ml_ai", "data_engineering"
}

TOPIC_FRIENDLY_NAMES = {
    "pune": "🏢 Pune Jobs",
    "bangalore": "🏢 Bangalore Jobs",
    "mumbai": "🏢 Mumbai/Thane Jobs",
    "hyderabad": "🏢 Hyderabad Jobs",
    "chennai": "🏢 Chennai Jobs",
    "delhi_ncr": "🏢 Delhi-NCR Jobs",
    "india": "🇮🇳 India (Onsite/Hybrid)",
    "india_remote": "🇮🇳 India Remote",
    "apac_remote": "🌏 APAC Remote",
    "global_remote": "🌍 Global Remote",
    "worldwide_remote": "🗺️ Worldwide Remote",
    "apac_jobs": "🌏 APAC (Onsite/Hybrid)",
    "eu_jobs": "🇪🇺 EU Jobs",
    "arab_jobs": "🇦🇪 Arab/Middle East",
    "visa_sponsored": "🛂 Visa Sponsored",
    "data_analytics": "📊 Data Analytics",
    "python_developer": "🐍 Python Developer",
    "data_scientist": "🧪 Data Scientist (Jr/Mid)",
    "ml_ai": "🤖 ML / AI (Jr/Mid)",
    "data_engineering": "💾 Data Engineering"
}


def clean_description(desc_html: str) -> str:
    """Strip all HTML tags and normalize spaces using BeautifulSoup after unescaping."""
    if not desc_html:
        return ""
    try:
        import html
        from bs4 import BeautifulSoup
        # Unescape first to convert escaped HTML like &lt;p&gt; to standard tags
        unescaped = html.unescape(desc_html)
        soup = BeautifulSoup(unescaped, "html.parser")
        text = soup.get_text(separator=" ")
        return " ".join(text.split())
    except Exception:
        import re
        clean = re.sub(r'<[^>]+>', '', desc_html)
        return " ".join(clean.split())


def extract_max_yoe(desc: str) -> int | None:
    """Extract the maximum required YoE from the description text using regex."""
    import re
    if not desc:
        return None
    patterns = [
        r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years|yoe|year)",
        r"(\d+)\+?\s*(?:years|yoe|year)\s*of\s*experience",
        r"(?:requried|require|minimum|least|at\s+least)\s*(\d+)\s*(?:years|yoe|year)"
    ]
    for p in patterns:
        matches = re.findall(p, desc.lower())
        if matches:
            for m in matches:
                if isinstance(m, tuple):
                    vals = [int(v) for v in m if v.isdigit()]
                    if vals:
                        return max(vals)
                elif str(m).isdigit():
                    return int(m)
    return None


def classify_job_topics(job: Job) -> List[str]:
    """Classify a job into highly targeted geographical and role-based topics."""
    import re
    topics = []
    title = (job.title or "").lower()
    desc = (job.description or "").lower()
    loc = (job.location or "").lower()
    
    # 1. Geographies
    # Pune
    if "pune" in loc or "pune" in title:
        topics.append("pune")
    # Bangalore
    if any(x in loc or x in title for x in ["bangalore", "bengaluru", "blr", "bang"]):
        topics.append("bangalore")
    # Mumbai (includes Navi Mumbai and Thane)
    if any(x in loc or x in title for x in ["mumbai", "navi mumbai", "thane"]):
        topics.append("mumbai")
    # Hyderabad
    if "hyderabad" in loc or "hyderabad" in title:
        topics.append("hyderabad")
    # Chennai
    if "chennai" in loc or "chennai" in title:
        topics.append("chennai")
    # Delhi NCR / Noida / Gurgaon
    if any(x in loc or x in title for x in ["delhi", "ncr", "noida", "gurgaon", "gurugram"]):
        topics.append("delhi_ncr")

    # Generic India (onsite/hybrid or remote)
    is_in_india = (
        re.search(r"\b(india|in)\b", loc) is not None or 
        re.search(r"\b(india|in)\b", title) is not None or
        any(x in loc or x in title for x in ["pune", "bangalore", "bengaluru", "mumbai", "navi mumbai", "thane", "hyderabad", "chennai", "delhi", "noida", "gurgaon", "gurugram", "ncr"])
    )
    if is_in_india:
        topics.append("india")
        
    is_remote = "remote" in loc or "remote" in title
    if is_remote:
        # India Remote
        if is_in_india:
            topics.append("india_remote")
        # APAC Remote
        elif any(x in loc or x in title for x in ["apac", "asia", "singapore", "sg", "philippines", "ph", "malaysia", "vietnam", "thailand", "indonesia"]):
            topics.append("apac_remote")
        # EU Remote
        elif any(x in loc or x in title for x in ["germany", "de", "france", "fr", "netherlands", "nl", "spain", "es", "italy", "it", "poland", "pl", "sweden", "se", "belgium", "be", "austria", "at", "europe", "eu"]):
            topics.append("eu_jobs")
        # Arab/ME Remote
        elif any(x in loc or x in title for x in ["dubai", "uae", "saudi", "ksa", "qatar", "bahrain", "kuwait", "oman", "middle east"]):
            topics.append("arab_jobs")
            
        # Worldwide Remote
        if any(x in loc or x in title for x in ["worldwide", "global", "anywhere", "open to all"]):
            topics.append("worldwide_remote")
        # Fallback Global Remote (excluding EU/US restricted)
        elif not any(x in loc for x in ["germany", "de", "us", "uk", "canada", "ca", "europe", "eu"]):
            topics.append("global_remote")
    else:
        # Onsite APAC
        if any(x in loc for x in ["singapore", "malaysia", "philippines", "vietnam", "thailand", "indonesia"]):
            topics.append("apac_jobs")
        # Onsite EU
        if any(x in loc for x in ["germany", "france", "netherlands", "spain", "italy", "poland", "sweden", "belgium", "austria"]):
            topics.append("eu_jobs")
        # Onsite Arab/ME
        if any(x in loc for x in ["dubai", "uae", "saudi", "ksa", "qatar", "bahrain", "kuwait", "oman"]):
            topics.append("arab_jobs")
            
    if "visa" in desc or "sponsorship" in desc or getattr(job, "visa_sponsorship", False):
        if not any(x in desc for x in ["no visa", "cannot sponsor", "do not sponsor"]):
            topics.append("visa_sponsored")

    # 2. Roles (filtered by max 5 YoE Ceiling for technical roles)
    max_yoe = extract_max_yoe(desc) or extract_max_yoe(title)
    
    # Check if this job requires senior YoE (> 5 YoE)
    is_junior_mid = True
    if max_yoe is not None and max_yoe > 5:
        is_junior_mid = False

    # Apply role tagging if it matches keywords and doesn't exceed 5 YoE
    if is_junior_mid:
        analytics_keywords = ["analytics", "analyst", "bi dev", "bi developer", "power bi", "tableau", "business intelligence"]
        if any(x in title for x in analytics_keywords):
            topics.append("data_analytics")
            
        if "python" in title and "developer" in title or "python engineer" in title:
            topics.append("python_developer")
            
        if "data scientist" in title or "data science" in title:
            topics.append("data_scientist")
                
        if any(x in title for x in ["machine learning", "ml ", "ml engineer", "artificial intelligence", "ai engineer", "deep learning"]):
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


def make_profile_keyboard() -> dict:
    """Generate inline buttons for editing user profile settings."""
    return {
        "inline_keyboard": [
            [
                {"text": "⏳ Edit YoE", "callback_data": "prof:edit_yoe"},
                {"text": "🛠️ Edit Skills", "callback_data": "prof:edit_skills"}
            ],
            [
                {"text": "📍 Edit Locations", "callback_data": "prof:edit_locs"},
                {"text": "📱 Main Menu", "callback_data": "menu"}
            ]
        ]
    }


def make_yoe_keyboard() -> dict:
    """Generate inline buttons for selecting YoE (0 to 10)."""
    buttons = []
    row = []
    for y in range(11):
        row.append({"text": str(y), "callback_data": f"prof_set_yoe:{y}"})
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"text": "🔙 Back", "callback_data": "prof:view"}])
    return {"inline_keyboard": buttons}


def calculate_user_match_score(job: Job, profile: dict) -> Tuple[float, List[str]]:
    """Calculate a personalized match score (0-100%) and matching reasons list."""
    import re
    score = 40.0 # Base score
    reasons = []
    
    title = (job.title or "").lower()
    desc = (job.description or "").lower()
    loc = (job.location or "").lower()
    
    # 1. Experience Check
    user_yoe = profile.get("yoe")
    if user_yoe is not None:
        job_max_yoe = extract_max_yoe(title) or extract_max_yoe(desc)
        if job_max_yoe is not None:
            if user_yoe >= job_max_yoe:
                score += 30.0
                reasons.append("⏳ Matches experience requirements")
            elif user_yoe < job_max_yoe - 2:
                score -= 30.0
                reasons.append("⚠️ Requires higher experience")
            else:
                score += 10.0
                reasons.append("⏳ Slighly higher experience requirements")
        else:
            score += 20.0
            reasons.append("⏳ Experience range likely fits")

    # 2. Location Check
    pref_locs_str = profile.get("locations")
    if pref_locs_str:
        pref_locs = [x.strip().lower() for x in pref_locs_str.split(",") if x.strip()]
        matched_locs = []
        for l in pref_locs:
            if l in loc or l in title:
                matched_locs.append(l)
        if matched_locs:
            score += 20.0
            reasons.append(f"📍 Location match ({', '.join(matched_locs)})")
            
    # 3. Skills Check
    pref_skills_str = profile.get("skills")
    if pref_skills_str:
        pref_skills = [x.strip().lower() for x in pref_skills_str.split(",") if x.strip()]
        matched_skills = []
        for s in pref_skills:
            if re.search(r"\b" + re.escape(s) + r"\b", title) or re.search(r"\b" + re.escape(s) + r"\b", desc):
                matched_skills.append(s)
        if matched_skills:
            skill_bonus = min(30.0, len(matched_skills) * 10.0)
            score += skill_bonus
            reasons.append(f"🛠️ Matches skills ({', '.join(matched_skills)})")
            
    final_score = max(0.0, min(100.0, score))
    return final_score, reasons


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
            
            score_line = ""
            reasons_line = ""
            user_score = getattr(j, "user_match_score", None) or getattr(j, "match_score", None)
            if user_score is not None:
                score_line = f" | 🎯 Match: {int(user_score)}%"
                reasons = getattr(j, "user_match_reasons", [])
                if reasons:
                    reasons_line = f"   💡 {', '.join(reasons[:2])}\n"
            
            line = (
                f"{idx}. 💼 <b>{title}</b>\n"
                f"   🏢 {company} | 📍 {location}{score_line}\n"
                f"{reasons_line}"
                f"   ⏳ {ago} | 🔗 <a href='{apply_url}'>Apply</a>\n\n"
            )
            lines.append(line)
            
    return "".join(lines)


async def notify_telegram(jobs: List[Job]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip().strip('"').strip("'")
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
            # Skip low score / international on-site jobs
            score = getattr(j, "match_score", None)
            if score is not None and score < 30.0:
                logger.info(f"Skipping Telegram alert for low-match job: {j.title} (Score: {score}%)")
                continue

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
                    
            posted_time = format_posted_ago(j.date)
            
            text = (
                f"📢 <b>New Job Alert</b>\n\n"
                f"💼 <b>Role:</b> {title}\n"
                f"🏢 <b>Company:</b> {company}\n"
                f"📍 <b>Location:</b> {location}\n"
                f"📅 <b>Posted:</b> {posted_time}\n"
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
            sent_threads = set()
            
            for topic in matched_topics:
                thread_id = get_topic_thread_id(topic)
                if thread_id is not None:
                    sent_threads.add(thread_id)
            
            # If no threads are mapped, fall back to main channel/group
            if not sent_threads:
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
                    logger.error(f"Error sending Telegram notification to main chat: {e}")
            else:
                for thread_id in sent_threads:
                    payload = {
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                        "message_thread_id": thread_id
                    }
                    try:
                        await client.post(url, json=payload)
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Error sending Telegram notification to thread {thread_id}: {e}")


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
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'")
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
                
        elif data == "prof:view":
            user_id = callback_query.get("from", {}).get("id")
            first_name = callback_query.get("from", {}).get("first_name", "User")
            prof = get_user_profile(user_id)
            if not prof:
                save_user_profile(user_id, first_name, None, None, None)
                prof = {"yoe": None, "skills": None, "locations": None}
            
            yoe_val = f"{prof['yoe']} YoE" if prof['yoe'] is not None else "Not set"
            skills_val = prof['skills'] if prof['skills'] else "Not set"
            locs_val = prof['locations'] if prof['locations'] else "Not set"
            
            msg = (
                f"👤 <b>Your Job Seeker Profile:</b>\n\n"
                f"⏳ <b>Experience:</b> {yoe_val}\n"
                f"🛠️ <b>Skills:</b> <code>{skills_val}</code>\n"
                f"📍 <b>Locations:</b> <code>{locs_val}</code>\n\n"
                f"Use the buttons below to customize your preferences."
            )
            await edit_reply(msg, make_profile_keyboard())
            
        elif data == "prof:edit_yoe":
            await edit_reply("⏳ <b>Select your years of experience (YoE):</b>", make_yoe_keyboard())
            
        elif data.startswith("prof_set_yoe:"):
            yoe = int(data.split(":")[1])
            user_id = callback_query.get("from", {}).get("id")
            first_name = callback_query.get("from", {}).get("first_name", "User")
            prof = get_user_profile(user_id) or {"skills": None, "locations": None}
            save_user_profile(user_id, first_name, yoe, prof.get("skills"), prof.get("locations"))
            await edit_reply(f"✅ Years of experience updated to <b>{yoe} YoE</b>!", make_yoe_keyboard())
            
        elif data == "prof:edit_skills":
            await edit_reply(
                "🛠️ <b>Update Skills:</b>\n\n"
                "Type the <code>/skills</code> command followed by a comma-separated list of your technical skills:\n\n"
                "Example:\n"
                "<code>/skills python, sql, machine learning</code>",
                make_profile_keyboard()
            )
            
        elif data == "prof:edit_locs":
            await edit_reply(
                "📍 <b>Update Locations:</b>\n\n"
                "Type the <code>/locations</code> command followed by a comma-separated list of preferred locations/cities:\n\n"
                "Example:\n"
                "<code>/locations pune, bangalore, remote</code>",
                make_profile_keyboard()
            )
            
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

    user_id = message.get("from", {}).get("id")
    first_name = message.get("from", {}).get("first_name", "User")

    if text.startswith("/profile"):
        prof = get_user_profile(user_id)
        if not prof:
            save_user_profile(user_id, first_name, None, None, None)
            prof = {"yoe": None, "skills": None, "locations": None}
            
        yoe_val = f"{prof['yoe']} YoE" if prof['yoe'] is not None else "Not set"
        skills_val = prof['skills'] if prof['skills'] else "Not set"
        locs_val = prof['locations'] if prof['locations'] else "Not set"
        
        msg = (
            f"👤 <b>Your Job Seeker Profile:</b>\n\n"
            f"⏳ <b>Experience:</b> {yoe_val}\n"
            f"🛠️ <b>Skills:</b> <code>{skills_val}</code>\n"
            f"📍 <b>Locations:</b> <code>{locs_val}</code>\n\n"
            f"Use the buttons below to customize your preferences."
        )
        await send_reply(msg, make_profile_keyboard())
        return {"ok": True}

    elif text.startswith("/skills"):
        cmd_parts = text.split(maxsplit=1)
        skills = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
        if not skills:
            await send_reply("⚠️ Usage: <code>/skills python, sql, machine learning</code>")
            return {"ok": True}
            
        prof = get_user_profile(user_id) or {"yoe": None, "locations": None}
        save_user_profile(user_id, first_name, prof.get("yoe"), skills, prof.get("locations"))
        await send_reply(f"✅ Skills updated to: <code>{skills}</code>")
        return {"ok": True}

    elif text.startswith("/locations"):
        cmd_parts = text.split(maxsplit=1)
        locs = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
        if not locs:
            await send_reply("⚠️ Usage: <code>/locations pune, bangalore, remote</code>")
            return {"ok": True}
            
        prof = get_user_profile(user_id) or {"yoe": None, "skills": None}
        save_user_profile(user_id, first_name, prof.get("yoe"), prof.get("skills"), locs)
        await send_reply(f"✅ Preferred locations updated to: <code>{locs}</code>")
        return {"ok": True}

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
        cmd_parts = text.split(maxsplit=1)
        param = cmd_parts[1].strip().lower() if len(cmd_parts) > 1 else ""
        
        if not param:
            if thread_id is None:
                await send_reply("⚠️ Please run this command inside a specific topic thread to link it.")
                return {"ok": True}
            menu_msg = "🔗 <b>Select a topic to link to this thread:</b>"
            await send_reply(menu_msg, make_link_menu_keyboard(thread_id))
            return {"ok": True}
            
        topic = param
            
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
        cmd_parts = text.split(maxsplit=1)
        topic = cmd_parts[1].strip().lower() if len(cmd_parts) > 1 else ""
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
        cmd_parts = text.split(maxsplit=1)
        query = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
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
                
        profile = get_user_profile(user_id)
        if profile:
            scored_matched = []
            for j in matched:
                score, reasons = calculate_user_match_score(j, profile)
                setattr(j, "user_match_score", score)
                setattr(j, "user_match_reasons", reasons)
                scored_matched.append(j)
            scored_matched.sort(key=lambda x: (getattr(x, "user_match_score", 0.0), getattr(x, "date", datetime.utcnow()) or datetime.utcnow()), reverse=True)
            matched = scored_matched
        else:
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
