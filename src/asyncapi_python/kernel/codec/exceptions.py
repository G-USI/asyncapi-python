"""Codec-related exceptions"""


class CodecError(Exception):
    """Base exception for codec-related errors"""
    pass


class EncodingError(CodecError):
    """Raised when encoding fails"""
    pass


class DecodingError(CodecError):
    """Raised when decoding fails"""
    pass


class CodecNotFoundError(CodecError):
    """Raised when no codec is registered for a content type"""
    pass


class ValidationError(CodecError):
    """Raised when message validation fails"""
    pass