import asyncio
import time

async def fetch_data(source, delay):
    await asyncio.sleep(delay)   # pretend this is a slow API call
    return f"fetching from... {source}"

async def main():
    start  = time.time()
    results = await asyncio.gather(
        fetch_data("Mumbai", 1),
        fetch_data("New York", 2),
        fetch_data("Tokyo", 3),
    )
    print(results)
    print(f"Took {time.time() - start:.1f} seconds")

asyncio.run(main())