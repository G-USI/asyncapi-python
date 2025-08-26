class UninitializedError(Exception):
    def __init__(self):
        super().__init__(
            "Tried to perform wire communication action before initializing wire"
        )
