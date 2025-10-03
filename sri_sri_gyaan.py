# SRI SRI GYAAN — inspiration-guided wisdom bot (class-safe + teacher dashboard)
import os, time, re, json, uuid, datetime, io
import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_TITLE = "🕊️ SRI SRI GYAAN"
DISCLAIMER = (
    "This assistant is *inspired by* Gurudev Sri Sri Ravi Shankar’s public teachings "
    "and general style (gentle, practical, meditation-centric). It is **not** the guru, "
    "does not quote his words, and does not claim endorsement."
)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
DEFAULT_LOGO = os.path.join(ASSETS_DIR, "logo.png")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
ANALYTICS_FILE = os.path.join(DATA_DIR, "analytics.jsonl")

BRAND = {"accent":"#1e88e5","accent_soft":"#e3f2fd","bg_card":"#ffffff","bg_page":"#f7f9fc","text_main":"#0f172a","text_soft":"#475569"}
THEME_CSS = f"""
<style>
.stApp {{ background: {BRAND['bg_page']}; }}
.sri-topbar {{
  padding: 14px 16px; background: linear-gradient(90deg, {BRAND['accent']} 0%, #7cb7ff 100%);
  border-radius: 14px; color: white; display:flex; align-items:center; gap:12px; margin-bottom:10px;
  box-shadow:0 6px 18px rgba(30,136,229,0.18);
}}
.sri-logo {{ width:40px; height:40px; border-radius:10px; background: rgba(255,255,255,0.2);
  display:flex; align-items:center; justify-content:center; font-size:22px; }}
.sri-title {{ font-weight:700; font-size:20px; letter-spacing:0.4px; }}
.sri-caption {{ color:#eef5ff; opacity:0.95; font-size:13px; margin-top:-2px; }}
.sri-metric {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:12px; margin:8px 0 18px; }}
.sri-metric > div {{ background:{BRAND['bg_card']}; border:1px solid #e6eef7; border-radius:14px; padding:12px; box-shadow:0 8px 24px rgba(16,24,40,0.04);}}
.sri-small {{ color:{BRAND['text_soft']}; font-size:12px; }}
</style>
"""

UI_STRINGS = {
 "en":{"welcome":"Welcome. Ask from the heart; we will answer with clarity and kindness.","config":"Configuration","model":"Model","practice":"Always add a micro-practice","words":"Word target","boundaries":"Boundaries","boundaries_text":"The assistant avoids impersonation and sensitive directives.","moderation":"Class-safe moderation","moderation_hint":"Blocks self-harm, hate, explicit, or targeted harassment terms.","daily_reflection":"Daily Reflection mode (1-minute practice before chat)","language":"Language","logo":"Sidebar logo (optional)","reflect_title":"Daily Reflection (1 minute)","reflect_body":"Sit comfortably. Breathe in 4, out 6 — ten rounds. Notice one thing you can appreciate today. When ready, start your conversation.","disclaimer":DISCLAIMER,"blocked":"Your message contains terms we don’t allow here. Try asking the essence without harmful or explicit wording.","nav":"Mode","nav_chat":"Chat","nav_dash":"Teacher Dashboard","dash_title":"Teacher Dashboard","dash_sub":"Aggregated, anonymized stats across sessions. No PII stored.","exp_csv":"Download this session transcript (CSV)","exp_analytics":"Download aggregated analytics (JSONL)","dash_metrics":["Questions","Blocks","Languages"]}
}

SYSTEM_PROMPT_BASE = """
You are 'SRI SRI GYAAN', an AI wisdom guide inspired by public, high-level themes. You are not a person.
No impersonation, no quotes, no endorsement claims. Original phrasing only.
Style: warm, simple, brief, practical spirituality (breath, meditation, service, gratitude), gentle humor, non-dogmatic insight.
Boundaries: no medical/legal/financial prescriptions; suggest professionals when needed. Avoid harm/self-harm/hate/violence. 150–250 words by default.

Format (flexible):
1) One-line essence (bold).
2) Short explanation (2–4 lines).
3) Micro-practice: 1–3 steps.
4) Optional one-line reassurance.
"""

DEFAULT_PRACTICE = [
 "Close your eyes for 60 seconds.",
 "Breathe in for 4 counts, out for 6 counts — five rounds.",
 "Place one gentle intention for today: ‘May I be useful.’",
]

SAFETY_HINTS = {
 "medical":"For personal medical concerns, please consult a qualified clinician. Breath and rest can support—not replace—care.",
 "legal":"For binding legal matters, consult a licensed attorney. This is reflective guidance, not legal advice.",
 "financial":"For investments or taxes, consult a certified professional. Consider decision hygiene and risk realism.",
}

BLOCKED_PATTERNS = [r"\bkill myself\b", r"\bsuicide\b", r"\bself[-\s]?harm\b", r"\bhate\s+[a-zA-Z]+\b", r"\bgenocide\b", r"\bexplicit\b", r"\bporn\b", r"\brape\b", r"\bhow to make (?:a )?bomb\b", r"\bkill (?:him|her|them)\b"]

def violates_policy(text: str) -> bool:
 t = text.lower()
 import re
 for pat in BLOCKED_PATTERNS:
  if re.search(pat, t):
   return True
 return False

def risk_domain(user_text: str) -> str | None:
 t = user_text.lower()
 if any(k in t for k in ["diagnose","prescribe","dose","my symptoms","treatment","medicine"]): return "medical"
 if any(k in t for k in ["lawsuit","contract","legal","court","divorce notice","section"]): return "legal"
 if any(k in t for k in ["invest","stock","mutual fund","returns","loan","tax","roi"]): return "financial"
 return None

def get_client():
 if OpenAI is None:
  st.error("openai package not available. Run: pip install openai")
  return None
 api_key = os.getenv("OPENAI_API_KEY","" )
 if not api_key:
  st.error("Missing OPENAI_API_KEY environment variable.")
  return None
 return OpenAI()

def llm_reply(client, messages, model_name: str):
 model = model_name or "gpt-4o-mini"
 resp = client.chat.completions.create(model=model, temperature=0.7, max_tokens=800, messages=messages)
 return resp.choices[0].message.content

def render_message(role, content):
 st.chat_message("user" if role=="user" else "assistant").markdown(content)

def multilingual_hint(lang_code: str) -> str:
 return "Respond only in English."

def daily_reflection_block(title: str, body: str):
 with st.expander(f"🕯️ {title}", expanded=True):
  st.write(body)
  st.progress(0); ph=st.empty()
  for i in range(60):
   ph.progress(int((i+1)/60*100)); time.sleep(0.02)
  st.success("You’re ready. Begin your question below.")

def session_id():
 if "sid" not in st.session_state: st.session_state.sid = uuid.uuid4().hex[:12]
 return st.session_state.sid

def log_event(event_type: str, lang: str, extra: dict | None = None):
 rec = {"ts": datetime.datetime.utcnow().isoformat()+"Z","sid": session_id(),"type": event_type,"lang": lang}
 if extra: rec.update(extra)
 try:
  os.makedirs(DATA_DIR, exist_ok=True)
  with open(os.path.join(DATA_DIR,"analytics.jsonl"),"a",encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False)+"\n")
 except Exception: pass

def read_analytics():
 out=[]; p=os.path.join(DATA_DIR,"analytics.jsonl")
 if os.path.exists(p):
  with open(p,"r",encoding="utf-8") as f:
   for line in f:
    try: out.append(json.loads(line))
    except Exception: continue
 return out

def export_current_transcript_csv(messages):
 import csv
 buf = io.StringIO(); w=csv.writer(buf); w.writerow(["role","content"])
 for m in messages[1:]: w.writerow([m["role"], m["content"]])
 return buf.getvalue().encode("utf-8")

def main():
 st.set_page_config(page_title=APP_TITLE, page_icon="🕊️", layout="centered")
 st.markdown(THEME_CSS, unsafe_allow_html=True)

 with st.sidebar:
  lang = st.selectbox("Language / भाषा", ["en"], index=0)
  strings = UI_STRINGS[lang]
  mode = st.radio(strings["nav"], [strings["nav_chat"], strings["nav_dash"]], index=0)

  st.header(strings["config"])
  if os.path.exists(DEFAULT_LOGO): st.image(DEFAULT_LOGO, caption="Default logo", width=100)
  logo_file = st.file_uploader(strings["logo"], type=["png","jpg","jpeg","webp"])
  daily_reflect = st.toggle(strings["daily_reflection"], value=False)
  moderation_on = st.toggle(strings["moderation"], value=True)
  model_name = st.text_input(strings["model"], value="gpt-4o-mini")
  practice_toggle = st.checkbox(strings["practice"], value=True, key="practice_toggle")
  word_target = st.slider(strings["words"], min_value=120, max_value=400, value=220, step=10)
  st.markdown("—"); st.subheader(strings["boundaries"]); st.write(strings["boundaries_text"])

 st.markdown('<div class="sri-topbar">', unsafe_allow_html=True)
 if 'logo_file' in locals() and logo_file is not None: st.image(logo_file, width=40)
 elif os.path.exists(DEFAULT_LOGO): st.image(DEFAULT_LOGO, width=40)
 else: st.markdown('<div class="sri-logo">🕊️</div>', unsafe_allow_html=True)
 st.markdown(f'<div><div class="sri-title">{APP_TITLE}</div><div class="sri-caption">{UI_STRINGS[lang]["disclaimer"]}</div></div>', unsafe_allow_html=True)
 st.markdown('</div>', unsafe_allow_html=True)

 if "messages" not in st.session_state:
  st.session_state.messages = [{"role":"system","content":SYSTEM_PROMPT_BASE},{"role":"assistant","content":UI_STRINGS[lang]["welcome"]}]
  log_event("session_start", "en")
 st.session_state.messages[0]["content"] = SYSTEM_PROMPT_BASE
 st.session_state.messages[1]["content"] = UI_STRINGS[lang]["welcome"]

 if mode == UI_STRINGS[lang]["nav_dash"]:
  st.header(UI_STRINGS[lang]["dash_title"]); st.caption(UI_STRINGS[lang]["dash_sub"])
  logs = read_analytics()
  q_count = sum(1 for r in logs if r.get("type")=="question")
  block_count = sum(1 for r in logs if r.get("type")=="blocked")
  lang_counts = {}; 
  for r in logs: lang_counts[r.get("lang","en")] = lang_counts.get(r.get("lang","en"),0)+1

  st.markdown('<div class="sri-metric">', unsafe_allow_html=True)
  st.markdown(f'<div><b>{UI_STRINGS[lang]["dash_metrics"][0]}:</b><br><span class="sri-small">{q_count}</span></div>', unsafe_allow_html=True)
  st.markdown(f'<div><b>{UI_STRINGS[lang]["dash_metrics"][1]}:</b><br><span class="sri-small">{block_count}</span></div>', unsafe_allow_html=True)
  st.markdown(f'<div><b>{UI_STRINGS[lang]["dash_metrics"][2]}:</b><br><span class="sri-small">{lang_counts}</span></div>', unsafe_allow_html=True)
  st.markdown('</div>', unsafe_allow_html=True)

  csv_bytes = export_current_transcript_csv(st.session_state.messages)
  st.download_button(UI_STRINGS[lang]["exp_csv"], data=csv_bytes, file_name="transcript.csv", mime="text/csv")
  p = os.path.join(DATA_DIR,"analytics.jsonl")
  if os.path.exists(p):
   with open(p,"rb") as f:
    st.download_button(UI_STRINGS[lang]["exp_analytics"], data=f.read(), file_name="analytics.jsonl", mime="application/json")
  else:
   st.info("No analytics captured yet.")
  return

 if daily_reflect:
  daily_reflection_block(UI_STRINGS[lang]["reflect_title"], UI_STRINGS[lang]["reflect_body"])

 for m in st.session_state.messages[1:]: render_message(m["role"], m["content"])

 user_input = st.chat_input("Type your question...")
 if user_input:
  if moderation_on and violates_policy(user_input):
   st.warning(UI_STRINGS[lang]["blocked"])
   render_message("user", user_input); st.session_state.messages.append({"role":"user","content":user_input})
   render_message("assistant", UI_STRINGS[lang]["blocked"]); st.session_state.messages.append({"role":"assistant","content":UI_STRINGS[lang]["blocked"]})
   log_event("blocked", "en"); return
  else:
   render_message("user", user_input); st.session_state.messages.append({"role":"user","content":user_input}); log_event("question", "en")
   domain = risk_domain(user_input); boundary_line = SAFETY_HINTS.get(domain, "") if domain else ""
   aux = f"Try to keep the answer near {word_target} words. Include a micro-practice box. Respond only in English."
   messages = [st.session_state.messages[0], *[m for m in st.session_state.messages[1:] if m['role']!='system'], {"role":"user","content":user_input}, {"role":"system","content":aux}]
   client = get_client(); 
   if client is None: return
   with st.chat_message("assistant"):
    with st.spinner("Reflecting..."):
     try:
      content = llm_reply(client, messages, model_name)
     except Exception as e:
      st.error(f"LLM error: {e}"); return
     if boundary_line: content = content.strip()+ "\n\n---\n" + f"_{boundary_line}_"
     if "Micro-practice" not in content:
      steps = "\n".join([f'{i+1}) {s}' for i,s in enumerate(DEFAULT_PRACTICE)]); content += f"\n\n**Micro-practice (60 seconds)**\n{steps}"
     st.markdown(content); st.session_state.messages.append({"role":"assistant","content":content})

 st.markdown("---"); st.caption("Class-safe, multilingual-ready, inspiration-guided. No impersonation, no quotes.")

if __name__ == "__main__":
 main()
