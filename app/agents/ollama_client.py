import instructor
from instructor import Instructor, AsyncInstructor

def get_ollama_client(model: str, async_mode: bool = False) -> Instructor | AsyncInstructor:
    client = instructor.from_provider(model,
                                      async_client=async_mode)

    return client