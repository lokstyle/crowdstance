# CrowdStance

> Cross-platform opinion retrieval and stance analysis across Reddit & Hacker News

CrowdStance is a web-based IR system that takes any topic or natural language query, fetches real comments from Reddit and Hacker News, classifies each comment as FOR / AGAINST / NUANCED using an LLM-based stance classifier, and surfaces structured insights including argument summaries, cross-platform divergence scores, subreddit breakdowns, and contrarian opinions.

## Features

- **Stance classification** — FOR / AGAINST / NUANCED with confidence scoring
- **Query intelligence** — natural language understanding and aspect-based disambiguation
- **Cross-platform divergence** — measures and explains how Reddit and HN communities differ
- **Argument summarizer** — grounded 2-sentence summaries per stance based on real comments
- **Subreddit breakdown** — see which communities lean which way
- **Minority opinion surfacing** — contrarian takes highlighted separately
- **Keyword extraction** — top discussion keywords, clickable to search
- **Compare mode** — analyze two topics side by side
- **Time filtering** — all time / past year / past month / past week
- **Result caching** — 6-hour TTL cache to minimize API costs
- **Dark mode** — toggle between light and dark

## Tech Stack

- **Backend** — Python, FastAPI, Uvicorn
- **Frontend** — HTML, CSS, Vanilla JS
- **Stance Classifier** — Anthropic Claude Haiku (via Anthropic API)
- **Data Sources** — Reddit public JSON API, HN Algolia API
- **Cache** — In-memory with TTL

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/crowdstance.git
cd crowdstance
```

### 2. Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your API key

Copy `.env.example` to `.env` and add your Anthropic API key:

```bash
cp .env.example .env
```

Edit `.env` and replace the placeholder with your actual key. Get a key at https://console.anthropic.com

### 5. Run the app

```bash
uvicorn api:app --reload
```

Open http://localhost:8000 in your browser.

---

## Usage

1. Enter a topic or natural language question (e.g. "why do people hate Tesla service?")
2. Select platform: Both / Reddit only / HN only
3. Optionally open Advanced options to filter by subreddit, comment limit, or time range
4. Hit **Analyze →**
5. The query intelligence layer will suggest specific angles to narrow your search
6. Results show stance breakdown, argument summaries, divergence score, subreddit breakdown, and individual comments with source links

---

## Project Structure

```
crowdstance/
├── api.py                 # FastAPI backend, endpoints, caching, rate limiting
├── reddit_fetcher.py      # Reddit public JSON API fetcher
├── hn_fetcher.py          # Hacker News Algolia API fetcher
├── stance_classifier.py   # LLM-based batch classifier + summarizer
├── main.py                # CLI version for testing
├── test.py                # Automated test suite (33 tests)
├── static/
│   └── index.html         # Frontend
├── .env.example           # API key template
├── requirements.txt       # Python dependencies
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serves frontend |
| POST | `/analyze` | Run full stance analysis |
| POST | `/compare` | Compare two topics side by side |
| POST | `/intelligence` | Query understanding and aspect extraction |
| GET | `/health` | Health check and cache stats |
| DELETE | `/cache` | Clear result cache |

---

## Notes

- No Reddit API credentials needed — uses Reddit's public JSON API
- Anthropic API key required for stance classification and summarization
- Future versions will support additional LLM providers (OpenAI, Gemini, etc.)
- For production deployment: swap in-memory cache for Redis, add a task queue, containerize with Docker

---


