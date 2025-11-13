from abc import ABC, abstractmethod
from typing import Callable, Generic, TypedDict, Union, overload

from typing_extensions import Unpack

from ...typing import BatchConfig, Handler, T_Input, T_Output
from .params import HandlerParams

__all__ = ["Send", "Receive"]


class Send(ABC, Generic[T_Input, T_Output]):
    """An interface that sending endpoint implements"""

    class RouterInputs(TypedDict):
        """Base inputs for send endpoints. Router subclasses can extend this with specific parameters."""

        pass  # Empty for now, extensible for future fields

    @abstractmethod
    async def __call__(
        self, payload: T_Input, /, **kwargs: Unpack[RouterInputs]
    ) -> T_Output: ...


class Receive(ABC, Generic[T_Input, T_Output]):

    @overload
    def __call__(
        self, fn: Handler[T_Input, T_Output]
    ) -> Handler[T_Input, T_Output]: ...

    @overload
    def __call__(
        self,
        fn: None = None,
        *,
        batch: BatchConfig,
        **kwargs: Unpack[HandlerParams],
    ) -> Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]: ...

    @overload
    def __call__(
        self, fn: None = None, **kwargs: Unpack[HandlerParams]
    ) -> Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]]: ...

    @abstractmethod
    def __call__(
        self,
        fn: Handler[T_Input, T_Output] | None = None,
        *,
        batch: BatchConfig | None = None,
        **kwargs: Unpack[HandlerParams],
    ) -> Union[
        Handler[T_Input, T_Output],
        Callable[[Handler[T_Input, T_Output]], Handler[T_Input, T_Output]],
    ]: ...
