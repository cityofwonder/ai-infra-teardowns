from fastapi import FastAPI, Depends, Header, HTTPException

app = FastAPI()

def verify_token(authorization: str = Header(None)):
    print("[Depends] 1. Intercepting Request: Checking Token...")
    if authorization != "Bearer valid-jwt-token":
        print("[Depends] 1-X. Blocked! 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Invalid Token")
    print("[Depends] 2. Allowed! User identified as 'admin_user'")
    return "admin_user"

@app.post("/api/v1/build")
def execute_component(payload: dict, current_user: str = Depends(verify_token)):
    print(f"[Endpoint] 3. Starting Graph Execution Engine for '{current_user}'...")
    print(f"[Endpoint] 4. Running Python exec() on flow: {payload['flow_id']}")
    print(f"[Endpoint] 5. Execution Finished!")
    return {"status": "success", "executed_by": current_user}
