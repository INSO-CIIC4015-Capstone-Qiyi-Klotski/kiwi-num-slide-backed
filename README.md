## Prerequisites
- Docker installed and configured.

## Run with Docker
~~~bash
docker build -t qk-backend .
docker run --rm -p 8000:80 qk-backend
~~~

Open http://localhost:8000  
API docs: http://localhost:8000/docs

> Rebuild the image after code changes to see updates.