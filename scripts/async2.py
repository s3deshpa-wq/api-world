import asyncio
import time


async def fetch_data(source, delay):
    await asyncio.sleep(delay)  # pretend this is a slow API call
    return f"fetching from... {source}"


async def main():
    start = time.time()
    #    results = await asyncio.gather(
    a1 = await fetch_data("Mumbai", 1)
    a2 = await fetch_data("New York", 2)
    a3 = await fetch_data("Tokyo", 3)


    print(f"Took {time.time() - start:.1f} seconds")
    print(a1, a2, a3)

asyncio.run(main())