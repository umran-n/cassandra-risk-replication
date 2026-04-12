class CassandraAPIError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{status_code}] {message}")


class AuthError(CassandraAPIError):
    pass


class RateLimitError(CassandraAPIError):
    def __init__(self, status_code, message, retry_after=None):
        super().__init__(status_code, message)
        self.retry_after = retry_after
