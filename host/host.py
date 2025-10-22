import asyncio
import argparse

async def main():
    parser = argparse.ArgumentParser(description="MI Diagnostics Host")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()
    print(f"Starting server on {args.bind}:{args.port}")
    
if __name__ == "__main__":
    asyncio.run(main())