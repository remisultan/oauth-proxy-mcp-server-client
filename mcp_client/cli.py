import asyncio
from settings import ClientSettings
from client import SimpleAuthClient


async def main():
    settings = ClientSettings()
    print(f"🚀 Connecting to {settings.server_url} using {settings.transport_type}")
    client = SimpleAuthClient(settings.server_url, settings.transport_type)
    await client.connect()


def cli():
    asyncio.run(main())


if __name__ == "__main__":
    cli()
