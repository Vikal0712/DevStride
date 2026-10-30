import hashlib
import logging
import secrets
import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Activity, ActivityHistory, CodingProgress, CodingQuestion, SessionRecord, User, UserPreference
from .schemas import ActivityIn, ActivityOut, CompleteIn, LoginIn, PasswordIn, ProfileIn, ProgressIn, RegisterIn, UserOut

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("devstride")
pwd = CryptContext(schemes=["argon2"], deprecated="auto")
COOKIE = "devstride_session"
@asynccontextmanager
async def lifespan(_app: FastAPI):
    with next(get_db()) as db:
        existing = set(db.scalars(select(CodingQuestion.title)).all())
        for category, titles in QUESTION_GROUPS.items():
            for title in titles:
                if title not in existing:
                    db.add(CodingQuestion(title=title, category=category, difficulty=QUESTION_DIFFICULTY[title], description=f"Practice {title}. Explain your approach and analyze time and space complexity."))
        db.commit()
    yield

app = FastAPI(title="DevStride API", version="1.0.0", lifespan=lifespan)
auth_attempts = defaultdict(deque)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "X-Requested-With"])

QUESTION_GROUPS = {
"Arrays": ["Two Sum","Best Time to Buy and Sell Stock","Maximum Subarray","Move Zeroes","Contains Duplicate","Product of Array Except Self","3Sum","Merge Intervals","Maximum Product Subarray","Container With Most Water","Subarray Sum Equals K","Search in Rotated Sorted Array","Sort Colors","Next Permutation","First Missing Positive","Trapping Rain Water","Longest Consecutive Sequence","Merge Sorted Array","Spiral Matrix","Maximum Sum Circular Subarray"],
"Strings": ["Valid Anagram","Valid Palindrome","Valid Parentheses","Longest Substring Without Repeating Characters","Reverse Words in a String","Group Anagrams","Longest Palindromic Substring","Longest Common Prefix","Implement strStr()","String to Integer (atoi)","Find All Anagrams in a String","Minimum Window Substring","Permutation in String","Palindromic Substrings","Decode String"],
"Linked Lists": ["Reverse Linked List","Linked List Cycle","Merge Two Sorted Lists","Remove Nth Node From End of List","Middle of the Linked List","Palindrome Linked List","Intersection of Two Linked Lists","Add Two Numbers","Reorder List","Copy List with Random Pointer"]}
QUESTION_DIFFICULTY = {
"Two Sum":"Easy","Best Time to Buy and Sell Stock":"Easy","Maximum Subarray":"Medium","Move Zeroes":"Easy","Contains Duplicate":"Easy","Product of Array Except Self":"Medium","3Sum":"Medium","Merge Intervals":"Medium","Maximum Product Subarray":"Medium","Container With Most Water":"Medium","Subarray Sum Equals K":"Medium","Search in Rotated Sorted Array":"Medium","Sort Colors":"Medium","Next Permutation":"Medium","First Missing Positive":"Hard","Trapping Rain Water":"Hard","Longest Consecutive Sequence":"Medium","Merge Sorted Array":"Easy","Spiral Matrix":"Medium","Maximum Sum Circular Subarray":"Medium",
"Valid Anagram":"Easy","Valid Palindrome":"Easy","Valid Parentheses":"Easy","Longest Substring Without Repeating Characters":"Medium","Reverse Words in a String":"Medium","Group Anagrams":"Medium","Longest Palindromic Substring":"Medium","Longest Common Prefix":"Easy","Implement strStr()":"Easy","String to Integer (atoi)":"Medium","Find All Anagrams in a String":"Medium","Minimum Window Substring":"Hard","Permutation in String":"Medium","Palindromic Substrings":"Medium","Decode String":"Medium",
"Reverse Linked List":"Easy","Linked List Cycle":"Easy","Merge Two Sorted Lists":"Easy","Remove Nth Node From End of List":"Medium","Middle of the Linked List":"Easy","Palindrome Linked List":"Easy","Intersection of Two Linked Lists":"Easy","Add Two Numbers":"Medium","Reorder List":"Medium","Copy List with Random Pointer":"Medium"}

def utcnow(): return datetime.now(timezone.utc)
def token_digest(token: str) -> str: return hashlib.sha256(token.encode()).hexdigest()

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    record = db.get(SessionRecord, token_digest(token)) if token else None
    if not record or record.expires_at.replace(tzinfo=timezone.utc) <= utcnow():
        if record: db.delete(record); db.commit()
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    user = db.get(User, record.user_id)
    if not user: raise HTTPException(status_code=401, detail="Please log in to continue.")
    return user

def csrf(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}: return
    origin = request.headers.get("origin", "").rstrip("/")
    if origin not in settings.allowed_origins or request.headers.get("x-requested-with") != "XMLHttpRequest":
        raise HTTPException(status_code=403, detail="Request origin could not be verified.")

def auth_rate_limit(request: Request):
    now = time.time(); key = request.client.host if request.client else "unknown"; attempts = auth_attempts[key]
    while attempts and attempts[0] < now - 60: attempts.popleft()
    if len(attempts) >= 12: raise HTTPException(429, "Too many authentication attempts. Try again in a minute.")
    attempts.append(now)

def session_cookie(response: Response, db: Session, user: User):
    token = secrets.token_urlsafe(48)
    db.add(SessionRecord(token_hash=token_digest(token), user_id=user.id, expires_at=utcnow() + timedelta(days=settings.session_days)))
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="none" if settings.cookie_secure else "lax", max_age=settings.session_days*86400, path="/")

def history(db: Session, user: User, activity: Activity | None, action: str):
    db.add(ActivityHistory(user_id=user.id, activity_id=activity.id if activity else None, action=action))

def owned_activity(db: Session, user: User, activity_id: int):
    item = db.scalar(select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id))
    if not item: raise HTTPException(status_code=404, detail="Activity not found.")
    return item

@app.middleware("http")
async def safe_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "public, max-age=300"
    return response

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try: db.execute(select(1))
    except Exception: raise HTTPException(503, "Database unavailable")
    return {"status": "ok"}

@app.post("/api/auth/register", response_model=UserOut, status_code=201, dependencies=[Depends(csrf), Depends(auth_rate_limit)])
def register(data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    has_founder = db.scalar(select(func.count(User.id)).where(User.is_admin.is_(True))) or 0
    user = User(full_name=data.full_name.strip(), username=data.username.lower(), email=str(data.email).lower(), password_hash=pwd.hash(data.password), is_admin=has_founder == 0)
    db.add(user)
    try: db.flush(); db.add(UserPreference(user_id=user.id)); db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "That username or email is already registered, or founder setup is finishing. Please retry.")
    session_cookie(response, db, user); db.commit(); db.refresh(user)
    logger.info("Account created id=%s", user.id)
    return user

@app.post("/api/auth/login", response_model=UserOut, dependencies=[Depends(csrf), Depends(auth_rate_limit)])
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    identity = data.identity.strip().lower()
    user = db.scalar(select(User).where((func.lower(User.email) == identity) | (func.lower(User.username) == identity)))
    if not user or not pwd.verify(data.password, user.password_hash): raise HTTPException(401, "Username or password is incorrect.")
    session_cookie(response, db, user); db.commit(); return user

@app.post("/api/auth/logout", status_code=204, dependencies=[Depends(csrf)])
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if token:
        record = db.get(SessionRecord, token_digest(token))
        if record: db.delete(record); db.commit()
    response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="none" if settings.cookie_secure else "lax")

@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user

@app.get("/api/activities")
def list_activities(due_date: date | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Activity).where(Activity.user_id == user.id)
    if due_date: query = query.where(Activity.due_date == due_date)
    query = query.order_by(Activity.due_date.is_(None), Activity.due_date, Activity.created_at.desc())
    return {"items": db.scalars(query.offset(offset).limit(limit)).all(), "limit": limit, "offset": offset}

@app.post("/api/activities", response_model=ActivityOut, status_code=201, dependencies=[Depends(csrf)])
def create_activity(data: ActivityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = Activity(user_id=user.id, **data.model_dump()); db.add(item); db.flush(); history(db,user,item,"created"); db.commit(); db.refresh(item); return item

@app.get("/api/activities/{activity_id}", response_model=ActivityOut)
def get_activity(activity_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)): return owned_activity(db,user,activity_id)

@app.put("/api/activities/{activity_id}", response_model=ActivityOut, dependencies=[Depends(csrf)])
def update_activity(activity_id: int, data: ActivityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item=owned_activity(db,user,activity_id)
    for key,value in data.model_dump().items(): setattr(item,key,value)
    history(db,user,item,"updated"); db.commit(); db.refresh(item); return item

@app.delete("/api/activities/{activity_id}", status_code=204, dependencies=[Depends(csrf)])
def delete_activity(activity_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item=owned_activity(db,user,activity_id); history(db,user,item,"deleted"); db.flush(); db.delete(item); db.commit()

@app.patch("/api/activities/{activity_id}/complete", response_model=ActivityOut, dependencies=[Depends(csrf)])
def complete_activity(activity_id: int, data: CompleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item=owned_activity(db,user,activity_id); item.is_completed=data.is_completed; item.completed_at=utcnow() if data.is_completed else None; history(db,user,item,"completed" if data.is_completed else "reopened"); db.commit(); db.refresh(item); return item

@app.get("/api/coding/questions")
def questions(category: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query=select(CodingQuestion).order_by(CodingQuestion.id)
    if category: query=query.where(CodingQuestion.category==category)
    return db.scalars(query).all()

@app.get("/api/coding/progress")
def coding_progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(CodingProgress).where(CodingProgress.user_id==user.id)).all()

@app.put("/api/coding/progress/{question_id}", dependencies=[Depends(csrf)])
def update_progress(question_id: int, data: ProgressIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    question=db.get(CodingQuestion,question_id)
    if not question: raise HTTPException(404,"Question not found.")
    record=db.scalar(select(CodingProgress).where(CodingProgress.user_id==user.id,CodingProgress.question_id==question_id))
    if not record: record=CodingProgress(user_id=user.id,question_id=question_id); db.add(record)
    record.is_solved=data.is_solved; record.solved_at=utcnow() if data.is_solved else None; record.personal_notes=data.personal_notes; db.commit(); db.refresh(record); return record

def count(db,user_id, start, end, completed=None):
    q=select(func.count(Activity.id)).where(Activity.user_id==user_id,Activity.created_at>=start,Activity.created_at<end)
    if completed is not None: q=q.where(Activity.is_completed==completed)
    return db.scalar(q) or 0

def analytics_data(user: User, db: Session, days: int):
    pref=db.scalar(select(UserPreference).where(UserPreference.user_id==user.id))
    try:
        from zoneinfo import ZoneInfo
        user_tz=ZoneInfo(pref.timezone if pref else "Asia/Kolkata")
    except Exception:
        user_tz=timezone.utc
    today=datetime.now(user_tz).date(); start=today-timedelta(days=days-1); start_dt=datetime.combine(start,datetime.min.time(),tzinfo=timezone.utc); end_dt=datetime.combine(today+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc)
    records=db.scalars(select(Activity).where(Activity.user_id==user.id,or_((Activity.created_at>=start_dt)&(Activity.created_at<end_dt),(Activity.completed_at>=start_dt)&(Activity.completed_at<end_dt)))).all()
    solved=db.scalar(select(func.count(CodingProgress.id)).where(CodingProgress.user_id==user.id,CodingProgress.is_solved.is_(True))) or 0
    day_counts={}
    for item in records:
        if item.is_completed and item.completed_at:
            completed=item.completed_at
            if completed.tzinfo is None: completed=completed.replace(tzinfo=timezone.utc)
            d=completed.astimezone(user_tz).date(); day_counts[d]=day_counts.get(d,0)+1
    daily=[{"date":(start+timedelta(days=i)).isoformat(),"label":(start+timedelta(days=i)).strftime("%a" if days<=7 else "%b %d"),"completed":day_counts.get(start+timedelta(days=i),0)} for i in range(days)]
    today_items=db.scalars(select(Activity).where(Activity.user_id==user.id,Activity.due_date==today)).all()
    total_today=len(today_items); done_today=sum(x.is_completed for x in today_items)
    completed_month=sum(x.is_completed and x.completed_at and x.completed_at.date()>=today.replace(day=1) for x in records)
    created_month=sum(x.created_at.date()>=today.replace(day=1) for x in records)
    total_complete=db.scalar(select(func.count(Activity.id)).where(Activity.user_id==user.id,Activity.is_completed.is_(True))) or 0
    total_activities=db.scalar(select(func.count(Activity.id)).where(Activity.user_id==user.id)) or 0
    category_rows=db.execute(select(Activity.category,func.count(Activity.id)).where(Activity.user_id==user.id).group_by(Activity.category).order_by(func.count(Activity.id).desc())).all()
    all_completed=db.scalars(select(Activity.completed_at).where(Activity.user_id==user.id,Activity.is_completed.is_(True),Activity.completed_at.is_not(None))).all()
    completed_dates=set()
    for completed in all_completed:
        if completed.tzinfo is None: completed=completed.replace(tzinfo=timezone.utc)
        completed_dates.add(completed.astimezone(user_tz).date())
    streak=0; cursor=today
    if cursor not in completed_dates: cursor-=timedelta(days=1)
    while cursor in completed_dates:
        streak+=1; cursor-=timedelta(days=1)
    recent=sorted((x for x in records if x.is_completed and x.completed_at),key=lambda x:x.completed_at,reverse=True)[:5]
    return {"daily":daily,"weekly":daily,"category_distribution":[{"category":name,"count":count} for name,count in category_rows],"recent_activity":[{"title":x.title,"category":x.category,"completed_at":x.completed_at} for x in recent],"summary":{"tasks_today":total_today,"completed_today":done_today,"pending_today":total_today-done_today,"current_streak":streak,"completion_rate":round(100*done_today/total_today) if total_today else 0,"completed_week":sum(x["completed"] for x in daily[-7:]),"completed_month":completed_month,"created_month":created_month,"coding_solved":solved,"all_time_completion_rate":round(100*total_complete/total_activities) if total_activities else 0}}

@app.get("/api/analytics/daily")
def analytics_daily(user:User=Depends(current_user),db:Session=Depends(get_db)): return analytics_data(user,db,1)
@app.get("/api/analytics/weekly")
def analytics_weekly(user:User=Depends(current_user),db:Session=Depends(get_db)): return analytics_data(user,db,7)
@app.get("/api/analytics/monthly")
def analytics_monthly(user:User=Depends(current_user),db:Session=Depends(get_db)):
    result=analytics_data(user,db,30)
    result["summary"]["completion_rate"]=result["summary"]["all_time_completion_rate"]
    return result

@app.get("/api/profile")
def get_profile(user:User=Depends(current_user),db:Session=Depends(get_db)):
    pref=db.scalar(select(UserPreference).where(UserPreference.user_id==user.id))
    if not pref: pref=UserPreference(user_id=user.id); db.add(pref); db.commit(); db.refresh(pref)
    return {"user":UserOut.model_validate(user),"theme":pref.theme,"timezone":pref.timezone}

@app.get("/api/admin/overview")
def admin_overview(user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not user.is_admin: raise HTTPException(403,"Founder access is required.")
    now=utcnow(); week_ago=now-timedelta(days=7); month_ago=now-timedelta(days=30)
    total=db.scalar(select(func.count(User.id))) or 0
    new_week=db.scalar(select(func.count(User.id)).where(User.created_at>=week_ago)) or 0
    new_month=db.scalar(select(func.count(User.id)).where(User.created_at>=month_ago)) or 0
    return {"total_users":total,"new_this_week":new_week,"new_last_30_days":new_month}

@app.put("/api/profile",response_model=UserOut,dependencies=[Depends(csrf)])
def update_profile(data:ProfileIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    user.full_name=data.full_name.strip(); user.username=data.username.lower(); user.email=str(data.email).lower()
    try:
        pref=db.scalar(select(UserPreference).where(UserPreference.user_id==user.id))
        if not pref: pref=UserPreference(user_id=user.id); db.add(pref)
        pref.theme=data.theme; pref.timezone=data.timezone; db.commit(); db.refresh(user)
    except IntegrityError: db.rollback(); raise HTTPException(409,"That username or email is already in use.")
    return user

@app.put("/api/profile/password",dependencies=[Depends(csrf)])
def change_password(data:PasswordIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not pwd.verify(data.current_password,user.password_hash): raise HTTPException(400,"Current password is incorrect.")
    user.password_hash=pwd.hash(data.new_password)
    db.query(SessionRecord).filter(SessionRecord.user_id==user.id).delete(synchronize_session=False); db.commit()
    return {"ok":True,"message":"Password updated. Please log in again."}

@app.delete("/api/profile",status_code=204,dependencies=[Depends(csrf)])
def delete_account(response:Response,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.delete(user); db.commit(); response.delete_cookie(COOKIE,path="/",secure=settings.cookie_secure,httponly=True,samesite="none" if settings.cookie_secure else "lax")
