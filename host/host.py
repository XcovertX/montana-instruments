import asyncio

async def main():
    await asyncio.sleep(1)  # Simulate some async work
    print("Hello, async world!")

if __name__ == "__main__":
    asyncio.run(main())