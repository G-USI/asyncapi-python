import json
from typing import Type, cast, ClassVar

from pydantic import BaseModel, ValidationError

from asyncapi_python.kernel.codec import Codec, CodecFactory
from asyncapi_python.kernel.document.message import Message


class JsonCodec(Codec[BaseModel, bytes]):
    """JSON codec that converts between Pydantic BaseModel and bytes"""
    
    def __init__(self, model_class: Type[BaseModel]):
        self._model_class = model_class
    
    def encode(self, payload: BaseModel) -> bytes:
        """Encode a Pydantic model to JSON bytes"""
        json_str = payload.model_dump_json()
        return json_str.encode('utf-8')
    
    def decode(self, payload: bytes) -> BaseModel:
        """Decode JSON bytes to a Pydantic model"""
        try:
            json_data = json.loads(payload.decode('utf-8'))
            return self._model_class.model_validate(json_data)
        except (json.JSONDecodeError, ValidationError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to decode JSON payload: {e}")


class JsonCodecFactory(CodecFactory[BaseModel, bytes]):
    """Factory for creating JSON codecs for Pydantic models
    
    This factory dynamically resolves Pydantic model classes from the generated code's
    messages.json module. It expects the following structure in the root module:
    
    root_module/
    ├── messages/
    │   └── json.py  # Contains all Pydantic model classes
    
    Model Resolution:
    - Converts message names to PascalCase class names (e.g., "user.created" -> "UserCreated")
    - Looks up the model class in root_module.messages.json
    - Creates a JsonCodec instance for the resolved model class
    
    Registry:
    - Caches codec instances to avoid creating them multiple times for the same message
    - Uses message specs as cache keys (message specs are hashable)
    - Shared across all JsonCodecFactory instances via class variable
    """
    
    _codec_registry: ClassVar[dict[Message, JsonCodec]] = {}
    
    def __init__(self, module):
        super().__init__(module)
    
    def create(self, message: Message) -> JsonCodec:
        """Creates a JSON codec instance from the message spec"""
        # Check if codec already exists in registry
        if message in self._codec_registry:
            return self._codec_registry[message]
        
        if not message.payload:
            raise ValueError("Message payload is required for JSON codec")
        
        # Try to resolve the model class from the module
        model_class = self._resolve_model_class(message)
        codec = JsonCodec(model_class)
        
        # Cache the codec in registry
        self._codec_registry[message] = codec
        return codec
    
    def _resolve_model_class(self, message: Message) -> Type[BaseModel]:
        """Resolve the Pydantic model class from the message"""
        if not message.name:
            raise ValueError("Message name is required to resolve model class")
        
        # Convert message name to expected class name (e.g., "user.created" -> "UserCreated")
        class_name = self._to_class_name(message.name)
        
        try:
            # Look for models in messages.json submodule
            messages_json_module = getattr(self._module, 'messages').json
            model_class = getattr(messages_json_module, class_name)
            if not issubclass(model_class, BaseModel):
                raise ValueError(f"Class {class_name} is not a Pydantic BaseModel")
            return cast(Type[BaseModel], model_class)
        except AttributeError as e:
            raise ValueError(f"Model class {class_name} not found in {self._module}.messages.json: {e}")
    
    def _to_class_name(self, message_name: str) -> str:
        """Convert message name to PascalCase class name"""
        # Handle dot-separated names like "user.created" -> "UserCreated"
        parts = message_name.replace('-', '_').replace('.', '_').split('_')
        return ''.join(part.capitalize() for part in parts if part)