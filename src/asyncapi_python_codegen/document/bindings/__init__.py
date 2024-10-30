from pydantic import BaseModel
from .amqp import AmqpBinding


class Bindings(BaseModel):
    amqp: AmqpBinding = AmqpBinding()
