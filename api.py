import os
import sys
from pathlib import Path
import pymysql
import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose.exceptions import JWTError

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

# Security configurations
SECRET_KEY = os.getenv("SALETAP", "SALETAP")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Database connections
from db_utils import get_mysql_connection  # Updated import

# Initialize FastAPI app
app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://saletap-nnrs.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- MODELS --------------------
class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    username: str | None = None
    role: str | None = None

# -------------------- AUTHENTICATION --------------------
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        return TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception

async def require_admin(user: TokenData = Depends(get_current_user)):
    if user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

# -------------------- ROUTES --------------------
@app.post("/api/auth/login", response_model=Token)
async def login(request: LoginRequest):
    conn = get_mysql_connection()  # Updated to MySQL
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, password, role_id FROM users WHERE username = %s",
            (request.username,)
        )
        user = cursor.fetchone()

        if not user or not verify_password(request.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        cursor.execute(
            "SELECT role_name FROM roles WHERE id = %s",
            (user["role_id"],)
        )
        role = cursor.fetchone()
        role_name = role["role_name"] if role else "Unknown"

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": request.username, "role": role_name},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": role_name
        }

    except pymysql.Error as e:  # Updated exception
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

# -------------------- PROTECTED ROUTES --------------------
@app.get("/api/reports/sales")
async def get_sales(
    start_date: str = Query(None),
    end_date: str = Query(None),
    user: TokenData = Depends(require_admin)
):
    conn = get_mysql_connection()  # Updated to MySQL
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    query = "SELECT id, total_amount, payment_method, date FROM sales"
    params = []
    if start_date and end_date:
        query += " WHERE date BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, tuple(params))
            sales = cursor.fetchall()
            return [dict(row) for row in sales]
    except pymysql.Error as e:  # Updated exception
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

@app.get("/api/reports/inventory")
async def get_inventory(user: TokenData = Depends(require_admin)):
    conn = get_mysql_connection()  # Updated to MySQL
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, quantity, price, barcode FROM inventory"
            )
            inventory = cursor.fetchall()

            for item in inventory:
                status = (
                    "Out of Stock" if item["quantity"] == 0 else
                    "Low Stock" if item["quantity"] < 5 else
                    "In Stock"
                )
                item["status"] = status
            
            return [dict(row) for row in inventory]
    except pymysql.Error as e:  # Updated exception
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000)