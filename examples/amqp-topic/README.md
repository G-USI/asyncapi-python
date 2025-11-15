# AMQP Topic Exchange Example

Demonstrates **parameterized channels with wildcard subscriptions** using AMQP topic exchanges.

## Overview

Weather alert system showing:
- Publishers send to specific routing keys (concrete parameters)
- Subscribers use wildcards (`*` and `#`) for pattern matching
- Topic exchange routes messages based on routing key patterns

## Architecture

```
Topic Exchange: weather_alerts
Channel: weather.{location}.{severity}

Routing Keys:
  weather.NYC.high
  weather.LA.low
  weather.CHI.critical
```

## Project Structure

```
examples/amqp-topic/
├── spec/
│   ├── common.asyncapi.yaml      # Shared channel/message definitions
│   ├── publisher.asyncapi.yaml   # Publisher app spec
│   ├── subscriber1.asyncapi.yaml # Subscriber 1 spec
│   └── subscriber2.asyncapi.yaml # Subscriber 2 spec
├── main-publisher.py             # Publisher implementation
├── main-subscriber1.py           # Subscriber 1 implementation
├── main-subscriber2.py           # Subscriber 2 implementation
├── Makefile                      # Build and run commands
└── README.md
```

## Usage

### 1. Generate Code

```bash
make generate
```

This generates type-safe Python code from AsyncAPI specs:
- `publisher/` - from `spec/publisher.asyncapi.yaml`
- `subscriber1/` - from `spec/subscriber1.asyncapi.yaml`
- `subscriber2/` - from `spec/subscriber2.asyncapi.yaml`

### 2. Run Publisher

```bash
make publisher
```

Publishes weather alerts to the topic exchange.

### 3. Run Subscribers

Terminal 1:
```bash
make subscriber1
```

Terminal 2:
```bash
make subscriber2
```

## Key Features

### Parameterized Channels

Channel address: `weather.{location}.{severity}`

Parameters are extracted from message payload:
```python
WeatherAlert(
    location="NYC",     # → {location}
    severity="high",    # → {severity}
    ...
)
# Creates routing key: weather.NYC.high
```

### Wildcard Subscriptions

Subscribers can use AMQP wildcards for pattern matching:
- `*` - Matches exactly one word
- `#` - Matches zero or more words

**This Example**:
- **Subscriber 1**: `weather.NYC.*` - All NYC alerts (any severity)
  - Uses `parameters={"location": "NYC"}`
  - Receives: NYC-HIGH
- **Subscriber 2**: `weather.*.critical` - Critical alerts (any location)
  - Uses `parameters={"severity": "critical"}`
  - Receives: CHI-CRITICAL

**Other Possible Patterns**:
- `weather.LA.*` - All LA alerts
- `weather.*.high` - High severity alerts from any location
- `weather.*.*` - ALL weather alerts (empty parameters)

### Parameter Validation

The runtime enforces:
- ✅ All required parameters must be provided
- ✅ Exact match required (strict validation)
- ✅ Queue bindings reject wildcards (concrete values only)
- ✅ Routing key bindings accept wildcards (pattern matching)

## Development

### Clean Up

```bash
make clean
```

Removes virtual environment and generated code.

### Help

```bash
make help
```

Shows available Makefile targets.

