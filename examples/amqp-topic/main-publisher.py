#!/usr/bin/env python3
"""
Weather Alert Publisher

Publishes weather alerts to an AMQP topic exchange with dynamic routing keys.
The routing key is built from the message payload fields (location and severity).

Example usage:
    python main-publisher.py
"""

import asyncio
from datetime import datetime, timezone
from os import environ

from asyncapi_python.contrib.wire.amqp import AmqpWire
from publisher import Application
from publisher.messages.json import WeatherAlert, Severity

# AMQP connection URI (can be overridden via environment variable)
AMQP_URI = environ.get("AMQP_URI", "amqp://guest:guest@localhost")

# Initialize application with AMQP wire
app = Application(AmqpWire(AMQP_URI))


async def main() -> None:
    """Main publisher routine"""
    print("🌤️  Weather Alert Publisher")
    print("=" * 50)
    print(f"Connecting to: {AMQP_URI}")

    # Start the application
    await app.start()
    print("✅ Connected to AMQP broker")
    print()

    # Sample weather alerts to publish
    alerts = [
        WeatherAlert(
            location="NYC",
            severity=Severity.HIGH,
            temperature=95,
            description="Heat wave warning in effect. Stay hydrated!",
            timestamp=datetime.now(timezone.utc),
        ),
        WeatherAlert(
            location="LA",
            severity=Severity.LOW,
            temperature=72,
            description="Sunny and pleasant weather expected.",
            timestamp=datetime.now(timezone.utc),
        ),
        WeatherAlert(
            location="CHI",
            severity=Severity.CRITICAL,
            temperature=5,
            description="Severe winter storm approaching. Travel not recommended.",
            timestamp=datetime.now(timezone.utc),
        ),
        WeatherAlert(
            location="MIA",
            severity=Severity.MEDIUM,
            temperature=88,
            description="Scattered thunderstorms expected this afternoon.",
            timestamp=datetime.now(timezone.utc),
        ),
        WeatherAlert(
            location="SEA",
            severity=Severity.LOW,
            temperature=65,
            description="Light rain throughout the day.",
            timestamp=datetime.now(timezone.utc),
        ),
    ]

    # Publish each alert
    print("📡 Publishing weather alerts...")
    print()

    for alert in alerts:
        # The routing key will be dynamically built as: weather.{location}.{severity}
        # For example: weather.NYC.high, weather.LA.low, etc.
        await app.producer.publish_weather_alert(alert)

        print(f"✉️  Published alert:")
        print(f"   Routing Key: weather.{alert.location}.{alert.severity.value}")
        print(f"   Location: {alert.location}")
        print(f"   Severity: {alert.severity.value}")
        print(f"   Temperature: {alert.temperature}°F")
        print(f"   Description: {alert.description}")
        print()

        # Small delay between messages for visibility
        await asyncio.sleep(0.5)

    print(f"✅ Published {len(alerts)} weather alerts")
    print()

    # Stop the application
    await app.stop()
    print("👋 Disconnected from AMQP broker")


if __name__ == "__main__":
    asyncio.run(main())
