import anthropic
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def strip_markdown(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-•]\s*', '', text, flags=re.MULTILINE)
    return text.strip()

def classify_batch(comments, query):
    if not comments:
        return []
    chunk_size = 20
    all_results = []
    for i in range(0, len(comments), chunk_size):
        chunk = comments[i:i+chunk_size]
        results = classify_chunk(chunk, query)
        all_results.extend(results)
    return all_results

def classify_chunk(comments, query):
    numbered = "\n\n".join([
        f"[{i+1}] {c['text'][:500]}" for i, c in enumerate(comments)
    ])

    prompt = f"""You are analyzing public opinion about: "{query}"

Classify each comment. Watch for:
- SARCASM: "Oh sure, X is GREAT" when clearly negative = AGAINST
- QUESTIONS: classify by the implied stance, not the question itself
- SHORT TAKES: even brief comments can have clear stances

Labels:
- FOR: supports, recommends, defends the topic
- AGAINST: opposes, criticizes, warns against the topic
- NUANCED: genuinely mixed, comparing pros/cons, or truly neutral

Also rate confidence 1-3 (3=very clear stance).
Also give a one-sentence reason for your classification.

{numbered}

Respond ONLY with a JSON array:
[{{"id":1,"stance":"FOR","confidence":2,"reason":"User recommends it despite minor issues"}}]

No markdown, no explanation, just the JSON array."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        text = re.sub(r'```json|```', '', text).strip()
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            text = match.group()
        results = json.loads(text)

        classified = []
        for i, comment in enumerate(comments):
            r = results[i] if i < len(results) else {"stance": "NUANCED", "confidence": 1, "reason": ""}
            stance = r.get("stance", "NUANCED").upper()
            if stance not in ["FOR", "AGAINST", "NUANCED"]:
                stance = "NUANCED"
            classified.append({
                **comment,
                "stance": stance,
                "confidence": r.get("confidence", 1),
                "reason": r.get("reason", "")
            })
        return classified

    except Exception as e:
        print(f"Classification error: {e}")
        return [{**c, "stance": "NUANCED", "confidence": 1, "reason": ""} for c in comments]

def summarize_stance(comments, stance, query):
    if not comments:
        return ""
    quality = [c for c in comments if len(c['text']) > 50][:12]
    if not quality:
        return ""
    texts = "\n".join([f"- {c['text'][:350]}" for c in quality])

    prompt = f"""Real comments from Reddit/HN about "{query}" — all expressing a {stance} position:

{texts}

Write exactly 2 sentences:
1. The main argument these people make (be specific, cite actual reasons they mention)
2. The most common specific concern or point they raise

No markdown, no bold, no headers, no asterisks, no bullet points. Plain text only."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=180,
            messages=[{"role": "user", "content": prompt}]
        )
        return strip_markdown(message.content[0].text)
    except Exception as e:
        print(f"Summary error: {e}")
        return ""

def generate_divergence_explanation(reddit_comments, hn_comments, query):
    if not reddit_comments or not hn_comments:
        return ""
    r_texts = "\n".join([f"- {c['text'][:200]}" for c in reddit_comments[:8]])
    h_texts = "\n".join([f"- {c['text'][:200]}" for c in hn_comments[:8]])

    prompt = f"""Topic: "{query}"

Reddit community says:
{r_texts}

Hacker News community says:
{h_texts}

In 2-3 sentences, explain WHY these two communities see this topic differently.
Focus on the cultural, demographic, or perspective differences — not just what they said.
Be specific and insightful.
No markdown, no bold, no headers, no asterisks. Plain text only."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return strip_markdown(message.content[0].text)
    except Exception as e:
        print(f"Divergence explanation error: {e}")
        return ""

def process_query_intelligence(query):
    prompt = f"""A user wants to analyze public opinion. Their input: "{query}"

Return a JSON object with:
{{
  "core_topic": "the main subject (1-3 words)",
  "search_queries": ["3-4 search terms to find relevant posts"],
  "intent": "complaints/praise/comparison/general",
  "aspects": ["up to 4 specific aspects people discuss"],
  "is_comparative": false
}}

Return ONLY the JSON object, no markdown."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        text = re.sub(r'```json|```', '', text).strip()
        return json.loads(text)
    except Exception as e:
        print(f"Query intelligence error: {e}")
        return {
            "core_topic": query,
            "search_queries": [query],
            "intent": "general",
            "aspects": [],
            "is_comparative": False
        }

def classify_all(comments, query):
    print(f"Classifying {len(comments)} comments in batch...")
    return classify_batch(comments, query)