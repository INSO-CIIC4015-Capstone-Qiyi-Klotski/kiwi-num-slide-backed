## Prerequisites
- Docker installed and configured.
- AWS CLI v2 configured (aws configure).
- Session Manager Plugin installed (check with: session-manager-plugin --version).

## Connect to RDS from local (bastion + SSM port-forward)

Open the tunnel (keep this terminal open):
```$ aws ssm start-session --region us-east-2 --target <Bastion-EC2-id> --document-name AWS-StartPortForwardingSessionToRemoteHost --parameters "host=<RDS-ENDPOINT>,portNumber=5432,localPortNumber=15432"```

Notes:
- If it works you’ll see: “Port 15432 opened… Waiting for connections…”


## Run locally with Docker

1) Create a `.env` file (do not commit) with 5 variables:
   - DB_HOST=host.docker.internal   <----- this is literally
   - DB_PORT=15432
   - DB_NAME=<your_db>
   - DB_USER=<your_user>
   - DB_PASSWORD=<your_password>

2) Build the image:
   - $ docker build -t qk-backend .

4) Run it mapping container 80 → local 8000 and loading `.env`
   
```$ docker run --rm -p 8000:80 --env-file .env qk-backend```

5) Test:
- App: http://localhost:8000/  and http://localhost:8000/health
- DB:  http://localhost:8000/db-ping



> Rebuild the image after code changes to see updates.

