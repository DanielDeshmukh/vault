import asyncio
import httpx

async def test():
    url = "https://ankenyiowa.gov/DocumentCenter/View/403/Employee-Handbook-PDF"
    print(f"Fetching {url}...")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get(url)
        ct = r.headers.get("content-type", "")
        print(f"Status: {r.status_code}, Content-Type: {ct}, Size: {len(r.content)}")

asyncio.run(test())
