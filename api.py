from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import hashlib
import json
import os
import time
import re
from collections import Counter, defaultdict

from reddit_fetcher import fetch_reddit_comments
from hn_fetcher import fetch_hn_comments
from stance_classifier import (
    classify_all, summarize_stance,
    generate_divergence_explanation, process_query_intelligence
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

cache = {}
CACHE_TTL = 21600

# Rate limiting
request_counts = defaultdict(list)
RATE_LIMIT = 10
RATE_WINDOW = 60

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    request_counts[ip] = [t for t in request_counts[ip] if now - t < RATE_WINDOW]
    if len(request_counts[ip]) >= RATE_LIMIT:
        return True
    request_counts[ip].append(now)
    return False

class QueryRequest(BaseModel):
    query: str
    platform: str = "both"
    subreddit: str = ""
    limit: int = 20
    time_filter: str = "all"

class CompareRequest(BaseModel):
    query_a: str
    query_b: str
    platform: str = "both"
    limit: int = 15
    time_filter: str = "all"

class IntelligenceRequest(BaseModel):
    query: str

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.post("/intelligence")
def get_intelligence(req: Request, request: IntelligenceRequest):
    if is_rate_limited(req.client.host):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return process_query_intelligence(request.query)

def get_cache_key(query, platform, subreddit, limit, time_filter):
    raw = f"{query}|{platform}|{subreddit}|{limit}|{time_filter}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_cache_valid(key):
    if key not in cache:
        return False
    if time.time() - cache[key]['timestamp'] > CACHE_TTL:
        del cache[key]
        return False
    return True

def deduplicate_comments(comments):
    seen = []
    unique = []
    for c in comments:
        text = c['text'].lower().strip()
        words = set(text.split())
        is_dup = False
        for s in seen:
            overlap = len(words & s) / max(len(words | s), 1)
            if overlap > 0.7:
                is_dup = True
                break
        if not is_dup:
            seen.append(words)
            unique.append(c)
    return unique

def get_confidence_distribution(comments):
    dist = {"high": 0, "medium": 0, "low": 0}
    for c in comments:
        conf = c.get("confidence", 1)
        if conf == 3:
            dist["high"] += 1
        elif conf == 2:
            dist["medium"] += 1
        else:
            dist["low"] += 1
    return dist

def get_minority_opinions(grouped):
    counts = {s: len(grouped[s]) for s in ["FOR", "AGAINST", "NUANCED"]}
    total = sum(counts.values())
    if total == 0:
        return None, []
    minority_stance = min(counts, key=counts.get)
    if counts[minority_stance] == 0:
        return None, []
    if counts[minority_stance] / total > 0.25:
        return None, []
    top = sorted(grouped[minority_stance], key=lambda x: x.get('score', 0), reverse=True)[:2]
    return minority_stance, top

def get_top_keywords(comments, query):
    stopwords = set(['the','a','an','is','it','in','on','at','to','for',
                     'of','and','or','but','not','with','this','that',
                     'are','was','were','be','been','have','has','had',
                     'do','did','does','will','would','could','should',
                     'i','you','he','she','we','they','my','your','his',
                     'her','our','their','its','what','how','why','when',
                     'where','who','which','just','like','so','if','can',
                     'get','got','also','than','more','very','really'])
    query_words = set(query.lower().split())
    word_counts = Counter()
    for c in comments:
        words = re.findall(r'\b[a-z]{4,}\b', c['text'].lower())
        for w in words:
            if w not in stopwords and w not in query_words:
                word_counts[w] += 1
    return [w for w, _ in word_counts.most_common(10)]

def run_analysis(query, platform, subreddit, limit, time_filter="all"):
    reddit_comments, hn_comments = [], []

    if platform in ["reddit", "both"]:
        reddit_comments = fetch_reddit_comments(
            query, limit=limit,
            subreddit=subreddit,
            time_filter=time_filter
        )

    if platform in ["hackernews", "both"]:
        hn_comments = fetch_hn_comments(
            query, limit=limit,
            time_filter=time_filter
        )

    all_raw = reddit_comments + hn_comments

    if not all_raw:
        return {
            "query": query,
            "grouped": {"FOR": [], "AGAINST": [], "NUANCED": []},
            "summaries": {"FOR": "", "AGAINST": "", "NUANCED": ""},
            "divergence_explanation": "",
            "divergence": 0,
            "reddit_ratio": {"FOR": 0, "AGAINST": 0, "NUANCED": 0},
            "hn_ratio": {"FOR": 0, "AGAINST": 0, "NUANCED": 0},
            "total": 0,
            "reddit_count": 0,
            "hn_count": 0,
            "subreddit_breakdown": {},
            "confidence_distribution": {"high": 0, "medium": 0, "low": 0},
            "minority_stance": None,
            "minority_comments": [],
            "top_keywords": [],
            "error": f"No comments found for '{query}'. Try a broader query, different time range, or different platform."
        }

    all_raw = deduplicate_comments(all_raw)
    reddit_comments = [c for c in all_raw if c['source'] == 'reddit']
    hn_comments = [c for c in all_raw if c['source'] == 'hackernews']

    reddit_classified = classify_all(reddit_comments, query)
    hn_classified = classify_all(hn_comments, query)
    all_classified = reddit_classified + hn_classified

    grouped = {"FOR": [], "AGAINST": [], "NUANCED": []}
    for comment in all_classified:
        grouped[comment["stance"]].append(comment)

    summaries = {}
    for stance in ["FOR", "AGAINST", "NUANCED"]:
        summaries[stance] = summarize_stance(grouped[stance], stance, query) if grouped[stance] else ""

    divergence_explanation = ""
    if reddit_classified and hn_classified:
        divergence_explanation = generate_divergence_explanation(
            reddit_classified, hn_classified, query
        )

    divergence, r_ratio, h_ratio = compute_divergence(reddit_classified, hn_classified)

    subreddit_breakdown = {}
    for c in reddit_classified:
        sub = c.get('subreddit', 'unknown')
        if not sub:
            sub = 'unknown'
        if sub not in subreddit_breakdown:
            subreddit_breakdown[sub] = {"FOR": 0, "AGAINST": 0, "NUANCED": 0, "total": 0}
        subreddit_breakdown[sub][c['stance']] += 1
        subreddit_breakdown[sub]['total'] += 1

    conf_dist = get_confidence_distribution(all_classified)
    minority_stance, minority_comments = get_minority_opinions(grouped)
    top_keywords = get_top_keywords(all_classified, query)

    return {
        "query": query,
        "grouped": grouped,
        "summaries": summaries,
        "divergence_explanation": divergence_explanation,
        "divergence": divergence,
        "reddit_ratio": r_ratio,
        "hn_ratio": h_ratio,
        "total": len(all_classified),
        "reddit_count": len(reddit_classified),
        "hn_count": len(hn_classified),
        "subreddit_breakdown": subreddit_breakdown,
        "confidence_distribution": conf_dist,
        "minority_stance": minority_stance,
        "minority_comments": minority_comments,
        "top_keywords": top_keywords,
        "error": None
    }

@app.post("/analyze")
def analyze(req: Request, request: QueryRequest):
    if is_rate_limited(req.client.host):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    key = get_cache_key(
        request.query, request.platform,
        request.subreddit, request.limit,
        request.time_filter
    )

    if is_cache_valid(key):
        print(f"Cache hit for '{request.query}'")
        return {**cache[key]['data'], "cached": True}

    result = run_analysis(
        request.query, request.platform,
        request.subreddit, request.limit,
        request.time_filter
    )

    cache[key] = {'data': result, 'timestamp': time.time()}
    return {**result, "cached": False}

@app.post("/compare")
def compare(req: Request, request: CompareRequest):
    if is_rate_limited(req.client.host):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
    if not request.query_a.strip() or not request.query_b.strip():
        raise HTTPException(status_code=400, detail="Both queries required")
    result_a = run_analysis(request.query_a, request.platform, "", request.limit, request.time_filter)
    result_b = run_analysis(request.query_b, request.platform, "", request.limit, request.time_filter)
    return {"a": result_a, "b": result_b}

@app.delete("/cache")
def clear_cache():
    cache.clear()
    return {"message": "Cache cleared"}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_entries": len(cache),
        "cache_ttl_hours": CACHE_TTL / 3600
    }

def compute_divergence(reddit_comments, hn_comments):
    def stance_ratio(comments):
        total = len(comments)
        if total == 0:
            return {"FOR": 0, "AGAINST": 0, "NUANCED": 0}
        return {
            "FOR": round(len([c for c in comments if c["stance"] == "FOR"]) / total * 100),
            "AGAINST": round(len([c for c in comments if c["stance"] == "AGAINST"]) / total * 100),
            "NUANCED": round(len([c for c in comments if c["stance"] == "NUANCED"]) / total * 100),
        }
    r = stance_ratio(reddit_comments)
    h = stance_ratio(hn_comments)
    divergence = sum(abs(r[s] - h[s]) for s in ["FOR", "AGAINST", "NUANCED"]) / 3
    return round(divergence, 1), r, h