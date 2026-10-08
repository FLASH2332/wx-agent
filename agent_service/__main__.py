import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "agent_service.api:create_app",
        factory=True,
        host=os.environ.get("HOST", "127.0.0.1"),  # use 0.0.0.0 inside a container
        port=int(os.environ.get("PORT", "3001")),
    )
