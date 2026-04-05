# Scraping Status

## Website Discovery (COMPLETE)
- 9,237 of 9,251 libraries have real website URLs (99.8%)
- Source: DuckDuckGo Lite search, 10 parallel batches
- 14 libraries remain with Google search fallback (mostly tiny/rural)

## Purchase Form Discovery (PARTIAL — 61% done)
- Scraped 5,452 of 8,418 unique library websites
- Found 2,365 verified purchase request form URLs
- Remaining: ~2,966 libraries still need scraping

### How to resume

The scraper deduplicates by website URL, so you can safely re-run from where it left off:

```bash
# Install dependencies if needed
pip3 install playwright
python3 -m playwright install chromium

# Resume scraping (starts at index 5452, batch of 842)
python3 scripts/scraper.py data scripts/scraper_results_resumed.json 5452 842
```

Or run multiple parallel batches:

```bash
python3 -u scripts/scraper.py data scripts/scraper_results_r0.json 5452 500 &
python3 -u scripts/scraper.py data scripts/scraper_results_r1.json 5952 500 &
python3 -u scripts/scraper.py data scripts/scraper_results_r2.json 6452 500 &
python3 -u scripts/scraper.py data scripts/scraper_results_r3.json 6952 500 &
python3 -u scripts/scraper.py data scripts/scraper_results_r4.json 7452 966 &
```

After scraping, merge results into data:

```bash
# Combine all result files
python3 -c "
import json, glob
all_r = []
for f in glob.glob('scripts/scraper_results*.json'):
    all_r.extend(json.load(open(f)))
with open('scripts/scraper_results_combined.json','w') as f:
    json.dump(all_r, f)
print(f'Combined {len(all_r)} results')
"

# Merge into data files (only applies high-confidence results)
python3 scripts/merge_scraper_results.py data scripts/scraper_results_combined.json

# Commit and deploy
git add data/
git commit -m "feat: merge additional scraper results"
git push origin main
vercel --yes --prod
```

## Notes
- Scraper uses non-headless Chromium (opens visible browser windows)
- ~17% of libraries have discoverable online purchase request forms
- Libraries without forms link to their homepage with a "submit it here" prompt
- Community submissions via the site fill gaps over time
