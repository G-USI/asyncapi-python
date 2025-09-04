import asyncio
from client import Application as ClientApp
from server import Application as ServerApp
from client.messages.json import Ping, Pong
from asyncapi_python.contrib.wire.in_memory import InMemoryWireFactory

# Use the same InMemory instance for both client and server
wire_factory = InMemoryWireFactory()

client = ClientApp(wire_factory)
server = ServerApp(wire_factory)

@server.consumer.onpingrequest
async def handle_ping_request(msg: Ping) -> Pong:
    print(f"Server handling request: {msg}")
    res = Pong()
    print(f"Server returning response: {res}")
    return res


async def main() -> None:
    # Start both applications
    await client.start()
    await server.start()
    
    # Send requests
    for i in range(3):
        req = Ping()
        print(f"Client sending request {i}: {req}")
        res = await client.producer.pingrequest(req)
        print(f"Client got response {i}: {res}")
    
    # Stop applications
    await client.stop()
    await server.stop()
    print("✅ RPC example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())