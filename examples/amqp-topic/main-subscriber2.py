#!/usr/bin/env python3
"""
Weather Alert Subscriber 2

Subscribes to weather alerts from an AMQP topic exchange.
This is the second subscriber - demonstrates multiple independent consumers.

Example usage:
    python main-subscriber2.py
"""

import asyncio
import signal
from os import environ
from types import FrameType

from asyncapi_python.contrib.wire.amqp import AmqpWire
from subscriber2 import Application
from subscriber2.messages.json import WeatherAlert

# AMQP connection URI (can be overridden via environment variable)
AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")

# Initialize application with AMQP wire
app = Application(AmqpWire(AMQP_URI))

# Shutdown event
shutdown_event = asyncio.Event()


def signal_handler(signum: int, frame: FrameType | None) -> None:
    """Handle shutdown signals"""
    print("\n⚠️  Shutdown signal received")
    shutdown_event.set()


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


@app.consumer.receive_weather_alert(parameters={"severity": "critical"})
async def handle_weather_alert(alert: WeatherAlert) -> None:
    """
    Handle incoming critical weather alerts.

    This handler subscribes to weather.*.critical pattern to receive
    all critical alerts regardless of location.
    """
    # Determine severity emoji
    severity_emoji = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }.get(alert.severity.value, "⚪")

    print(f"\n{severity_emoji} Weather Alert Received [SUBSCRIBER 2]")
    print(f"   Location: {alert.location}")
    print(f"   Severity: {alert.severity.value.upper()}")
    print(f"   Temperature: {alert.temperature}°F")
    print(f"   Description: {alert.description}")
    print(f"   Timestamp: {alert.timestamp}")


async def main() -> None:
    """Main subscriber routine"""
    print("🌤️  Weather Alert Subscriber 2")
    print("=" * 50)
    print(f"Connecting to: {AMQP_URI}")

    # Start the application
    await app.start()
    print("✅ Connected to AMQP broker")
    print("👂 Listening for weather alerts...")
    print("   (Press Ctrl+C to stop)")
    print()

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Stop the application
    print("\n🛑 Stopping subscriber...")
    await app.stop()
    print("👋 Disconnected from AMQP broker")


if __name__ == "__main__":
    asyncio.run(main())
