import requests
import time
import re

HEADERS = {"User-Agent": "crowdstance/1.0 (research project)"}

def clean_text(text):
    """Remove URLs, HTML, and garbage from comment text"""
    if not text:
        return ""
    # Remove URLs
    text = re.sub(r'http\S+|www\S+', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove Reddit markdown artifacts
    text = re.sub(r'\*+|\~\~|#+|&amp;|&gt;|&lt;', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_quality_comment(text):
    """Filter out low quality comments"""
    if not text or len(text) < 30:
        return False
    # Skip if mostly a URL
    if text.startswith('http') or text.startswith('www'):
        return False
    # Skip if it's just an image reference
    if any(x in text.lower() for x in ['i.redd.it', 'imgur.com', 'preview.redd']):
        return False
    # Skip deleted/removed
    if text.lower() in ['[deleted]', '[removed]', 'deleted', 'removed']:
        return False
    # Skip if too many special characters (bot/spam)
    alpha_ratio = sum(c.isalpha() for c in text) / len(text)
    if alpha_ratio < 0.5:
        return False
    return True

def fetch_post_comments(post_url, post_title, limit=10):
    """Fetch actual comments from a Reddit post thread"""
    try:
        json_url = post_url.rstrip('/') + '.json?limit=50&sort=top'
        response = requests.get(json_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return []

        data = response.json()
        if len(data) < 2:
            return []

        comments = []
        comment_listing = data[1]['data']['children']

        for child in comment_listing:
            if child['kind'] != 't1':
                continue
            body = child['data'].get('body', '')
            score = child['data'].get('score', 0)
            subreddit = child['data'].get('subreddit', '')
            permalink = child['data'].get('permalink', '')
            cleaned = clean_text(body)

            if is_quality_comment(cleaned):
                comments.append({
                    "text": cleaned,
                    "score": score,
                    "subreddit": subreddit,
                    "source": "reddit",
                    "url": f"https://reddit.com{permalink}" if permalink else "",
                    "context": post_title
                })

            if len(comments) >= limit:
                break

        return comments

    except Exception as e:
        print(f"Error fetching comments from {post_url}: {e}")
        return []

def fetch_reddit_comments(query, limit=20, subreddit="", time_filter="all"):
    """
    Search Reddit for posts about the query, then fetch comments from those posts.
    time_filter: 'day', 'week', 'month', 'year', 'all'
    """
    comments_per_post = 5
    posts_to_fetch = max(4, limit // comments_per_post)

    if subreddit:
        sub = subreddit.strip().lstrip("r/")
        url = f"https://www.reddit.com/r/{sub}/search.json?q={query}&restrict_sr=1&sort=relevance&t={time_filter}&limit={posts_to_fetch}"
    else:
        url = f"https://www.reddit.com/search.json?q={query}&sort=relevance&t={time_filter}&limit={posts_to_fetch}&type=link"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"Reddit search error: {response.status_code}")
            return []

        data = response.json()
        posts = data['data']['children']

        all_comments = []
        for post in posts:
            post_data = post['data']
            post_url = f"https://www.reddit.com{post_data.get('permalink', '')}"
            post_title = post_data.get('title', '')

            # Skip posts with no comments
            if post_data.get('num_comments', 0) == 0:
                continue

            post_comments = fetch_post_comments(post_url, post_title, limit=comments_per_post)
            all_comments.extend(post_comments)

            # Small delay to be respectful
            time.sleep(0.3)

            if len(all_comments) >= limit:
                break

        # Deduplicate by text similarity
        seen = set()
        unique = []
        for c in all_comments:
            key = c['text'][:80]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        print(f"Reddit: fetched {len(unique)} quality comments from {len(posts)} posts")
        return unique[:limit]

    except Exception as e:
        print(f"Reddit fetch error: {e}")
        return []