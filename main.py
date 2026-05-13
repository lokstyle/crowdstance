from reddit_fetcher import fetch_reddit_comments
from hn_fetcher import fetch_hn_comments
from stance_classifier import classify_all


def group_by_stance(comments):
    groups = {"FOR": [], "AGAINST": [], "NUANCED": []}
    for comment in comments:
        groups[comment["stance"]].append(comment)
    return groups


def compute_divergence(reddit_comments, hn_comments):
    def stance_ratio(comments):
        total = len(comments)
        if total == 0:
            return {"FOR": 0, "AGAINST": 0, "NUANCED": 0}
        return {
            "FOR": len([c for c in comments if c["stance"] == "FOR"]) / total,
            "AGAINST": len([c for c in comments if c["stance"] == "AGAINST"]) / total,
            "NUANCED": len([c for c in comments if c["stance"] == "NUANCED"]) / total,
        }

    r = stance_ratio(reddit_comments)
    h = stance_ratio(hn_comments)

    divergence = sum(abs(r[s] - h[s]) for s in ["FOR", "AGAINST", "NUANCED"]) / 3
    return round(divergence * 100, 1), r, h


def print_results(query, grouped, reddit_classified, hn_classified):
    print(f"\n{'=' * 60}")
    print(f"CrowdStance Results for: '{query}'")
    print(f"{'=' * 60}")

    for stance in ["FOR", "AGAINST", "NUANCED"]:
        comments = grouped[stance]
        print(f"\n--- {stance} ({len(comments)} comments) ---")
        top = sorted(comments, key=lambda x: x["score"], reverse=True)[:3]
        for c in top:
            print(f"  [{c['source']}] (score: {c['score']}) {c['text'][:150]}...")

    divergence, r_ratio, h_ratio = compute_divergence(reddit_classified, hn_classified)
    print(f"\n{'=' * 60}")
    print(f"Cross-Platform Divergence Score: {divergence}%")
    print(
        f"  Reddit  → FOR: {r_ratio['FOR']:.0%} | AGAINST: {r_ratio['AGAINST']:.0%} | NUANCED: {r_ratio['NUANCED']:.0%}")
    print(
        f"  HN      → FOR: {h_ratio['FOR']:.0%} | AGAINST: {h_ratio['AGAINST']:.0%} | NUANCED: {h_ratio['NUANCED']:.0%}")
    print(f"{'=' * 60}\n")


def run(query):
    print(f"Fetching Reddit comments for '{query}'...")
    reddit_comments = fetch_reddit_comments(query, limit=20)
    print(f"Got {len(reddit_comments)} Reddit comments")

    print(f"Fetching HN comments for '{query}'...")
    hn_comments = fetch_hn_comments(query, limit=20)
    print(f"Got {len(hn_comments)} HN comments")

    all_comments = reddit_comments + hn_comments
    print(f"\nClassifying {len(all_comments)} comments...")

    reddit_classified = classify_all(reddit_comments, query)
    hn_classified = classify_all(hn_comments, query)
    all_classified = reddit_classified + hn_classified

    grouped = group_by_stance(all_classified)
    print_results(query, grouped, reddit_classified, hn_classified)


if __name__ == "__main__":
    query = input("Enter a topic to analyze: ")
    run(query)