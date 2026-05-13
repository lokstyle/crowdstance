import requests
import html
import re
import time as time_module

def clean_text(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'http\S+|www\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_quality_comment(text):
    if not text or len(text) < 30:
        return False
    if text.startswith('http') or text.startswith('www'):
        return False
    alpha_ratio = sum(c.isalpha() for c in text) / len(text)
    if alpha_ratio < 0.5:
        return False
    return True

def get_timestamp(time_filter):
    now = int(time_module.time())
    map = {
        "day": now - 86400,
        "week": now - 604800,
        "month": now - 2592000,
        "year": now - 31536000,
    }
    return map.get(time_filter, 0)

def fetch_hn_comments(query, limit=20, time_filter="all"):
    base_url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=comment&hitsPerPage={limit*2}"

    if time_filter != "all":
        ts = get_timestamp(time_filter)
        base_url += f"&numericFilters=created_at_i>{ts}"

    try:
        response = requests.get(base_url, timeout=10)
        if response.status_code != 200:
            print(f"HN error: {response.status_code}")
            return []

        data = response.json()
        comments = []
        seen = set()

        for hit in data['hits']:
            text = clean_text(hit.get('comment_text', ''))
            if not is_quality_comment(text):
                continue

            key = text[:80]
            if key in seen:
                continue
            seen.add(key)

            score = hit.get('points') or hit.get('num_comments') or 0
            story_title = hit.get('story_title', '')
            object_id = hit.get('objectID', '')
            url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else ""

            comments.append({
                "text": text,
                "score": score,
                "source": "hackernews",
                "url": url,
                "context": story_title,
                "subreddit": ""
            })

            if len(comments) >= limit:
                break

        print(f"HN: fetched {len(comments)} quality comments")
        return comments

    except Exception as e:
        print(f"HN fetch error: {e}")
        return []