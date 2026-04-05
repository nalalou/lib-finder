"""Verify that library website URLs actually resolve.

Checks each library with a real website URL (not Google search fallback)
and removes URLs that are dead/broken, reverting them to the search fallback.
"""
import asyncio
import json
import glob
import os
import sys


async def check_url(session, url, timeout=10):
    """Check if a URL resolves. Returns True if reachable."""
    import aiohttp
    try:
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=timeout),
                                allow_redirects=True) as resp:
            return resp.status < 400
    except Exception:
        try:
            # Some servers reject HEAD, try GET
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                                   allow_redirects=True) as resp:
                return resp.status < 400
        except Exception:
            return False


async def verify_data_dir(data_dir, concurrency=20):
    """Verify all library URLs in the data directory.

    Libraries with dead URLs get reverted to Google search fallback.
    """
    import aiohttp

    files = sorted(glob.glob(os.path.join(data_dir, "libraries-*.json")))
    total = 0
    verified = 0
    dead = 0
    skipped = 0

    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector,
                                      headers={"User-Agent": "LibraryFinder/1.0"}) as session:
        for filepath in files:
            with open(filepath) as f:
                data = json.load(f)

            changed = False
            tasks = []

            for lib in data["libraries"]:
                total += 1
                url = lib["website"]

                # Skip Google search fallbacks
                if url.startswith("https://www.google.com/search"):
                    skipped += 1
                    continue

                tasks.append((lib, check_url(session, url)))

            # Run checks in batches
            if tasks:
                results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

                for (lib, _), is_ok in zip(tasks, results):
                    if is_ok is True:
                        verified += 1
                    else:
                        dead += 1
                        name = lib["name"]
                        city = lib["address"].split(",")[-2].strip() if "," in lib["address"] else ""
                        state = lib["address"].split(",")[-1].strip() if "," in lib["address"] else ""
                        search_query = f"{name} {city} {state} library".replace(" ", "+")
                        lib["website"] = f"https://www.google.com/search?q={search_query}"
                        changed = True
                        print(f"  DEAD: {name} -> {lib['website'][:60]}")

            if changed:
                with open(filepath, "w") as f:
                    json.dump(data, f, indent=2)

    print(f"\nURL Verification Complete:")
    print(f"  Total libraries: {total}")
    print(f"  Verified working: {verified}")
    print(f"  Dead/broken (reverted): {dead}")
    print(f"  No URL (skipped): {skipped}")
    return {"total": total, "verified": verified, "dead": dead, "skipped": skipped}


if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    print(f"Verifying URLs in {data_dir}/...")
    asyncio.run(verify_data_dir(data_dir))
