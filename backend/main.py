from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio
import uuid
import os
from pathlib import Path
import json
from datetime import datetime
import redis
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import aiofiles

# 既存の動画生成システムをインポート
from improved_styled_video_generator import ImprovedStyledVideoGenerator

app = FastAPI(
    title="ショート動画生成API",
    description="AI powered short video generation service",
    version="1.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],  # React アプリのURL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 設定
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://localhost:50021")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./video_generator.db")

# Redis接続
redis_client = redis.from_url(REDIS_URL)

# データベース設定
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# データベースモデル
class VideoGeneration(Base):
    __tablename__ = "video_generations"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    topic = Column(String)
    style = Column(String)
    status = Column(String)  # pending, processing, completed, failed
    script_data = Column(Text)
    video_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    plan = Column(String, default="free")  # free, premium, pro
    credits = Column(Integer, default=3)  # 月間クレジット
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

# テーブル作成
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class TopicSuggestionRequest(BaseModel):
    theme: str

class TopicSuggestion(BaseModel):
    title: str
    description: str
    estimated_views: str

class VideoGenerationRequest(BaseModel):
    topic: str
    style: str
    speaker_id: int = 1
    enable_preview: bool = False
    user_id: Optional[str] = None

class ScriptPreview(BaseModel):
    title: str
    style: str
    scenes: List[Dict[str, str]]

class VideoGenerationResponse(BaseModel):
    generation_id: str
    status: str
    estimated_time: int  # 推定完了時間（秒）

class VideoStatus(BaseModel):
    generation_id: str
    status: str
    progress: int  # 0-100
    current_step: str
    video_url: Optional[str] = None
    error_message: Optional[str] = None

# 動画生成システムのインスタンス
generator = ImprovedStyledVideoGenerator(OPENAI_API_KEY, VOICEVOX_URL)

@app.get("/")
async def root():
    return {"message": "ショート動画生成API v1.0", "status": "active"}

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    try:
        # VOICEVOX接続確認
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{VOICEVOX_URL}/speakers", timeout=5) as response:
                voicevox_status = response.status == 200
        
        # Redis接続確認
        redis_status = redis_client.ping()
        
        return {
            "status": "healthy",
            "voicevox": voicevox_status,
            "redis": redis_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/api/topics/suggest", response_model=List[TopicSuggestion])
async def suggest_topics(request: TopicSuggestionRequest):
    """テーマからお題提案"""
    try:
        suggestions = await generator.suggest_topics_from_theme(request.theme)
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"お題提案に失敗しました: {str(e)}")

@app.get("/api/styles")
async def get_available_styles():
    """利用可能なスタイル一覧"""
    styles = []
    for key, style in generator.image_styles.items():
        styles.append({
            "id": key,
            "name": style.name,
            "description": style.description,
            "consistency_keywords": style.consistency_keywords
        })
    return {"styles": styles}

@app.post("/api/script/preview", response_model=ScriptPreview)
async def preview_script(request: VideoGenerationRequest):
    """台本プレビュー生成"""
    try:
        script = await generator.generate_script(request.topic, request.style)
        return ScriptPreview(
            title=script["title"],
            style=script["style"],
            scenes=script["scenes"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"台本生成に失敗しました: {str(e)}")

@app.post("/api/video/generate", response_model=VideoGenerationResponse)
async def generate_video(
    request: VideoGenerationRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """動画生成開始"""
    try:
        # 生成IDを作成
        generation_id = str(uuid.uuid4())
        
        # データベースに記録
        db_generation = VideoGeneration(
            id=generation_id,
            user_id=request.user_id or "anonymous",
            topic=request.topic,
            style=request.style,
            status="pending"
        )
        db.add(db_generation)
        db.commit()
        
        # 非同期で動画生成を開始
        background_tasks.add_task(
            process_video_generation,
            generation_id,
            request.topic,
            request.style,
            request.speaker_id,
            request.enable_preview
        )
        
        return VideoGenerationResponse(
            generation_id=generation_id,
            status="pending",
            estimated_time=120  # 2分程度
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"動画生成開始に失敗しました: {str(e)}")

@app.get("/api/video/status/{generation_id}", response_model=VideoStatus)
async def get_video_status(generation_id: str, db: Session = Depends(get_db)):
    """動画生成状況確認"""
    db_generation = db.query(VideoGeneration).filter(VideoGeneration.id == generation_id).first()
    
    if not db_generation:
        raise HTTPException(status_code=404, detail="指定されたIDの動画生成が見つかりません")
    
    # Redisから進行状況を取得
    progress_data = redis_client.get(f"progress:{generation_id}")
    if progress_data:
        progress_info = json.loads(progress_data)
        progress = progress_info.get("progress", 0)
        current_step = progress_info.get("current_step", "準備中...")
    else:
        progress = 0 if db_generation.status == "pending" else 100
        current_step = "準備中..." if db_generation.status == "pending" else "完了"
    
    return VideoStatus(
        generation_id=generation_id,
        status=db_generation.status,
        progress=progress,
        current_step=current_step,
        video_url=db_generation.video_url,
        error_message=db_generation.error_message
    )

@app.get("/api/video/download/{generation_id}")
async def download_video(generation_id: str, db: Session = Depends(get_db)):
    """動画ダウンロード"""
    db_generation = db.query(VideoGeneration).filter(VideoGeneration.id == generation_id).first()
    
    if not db_generation or db_generation.status != "completed":
        raise HTTPException(status_code=404, detail="動画が見つからないか、まだ生成中です")
    
    if not db_generation.video_url or not os.path.exists(db_generation.video_url):
        raise HTTPException(status_code=404, detail="動画ファイルが見つかりません")
    
    return FileResponse(
        path=db_generation.video_url,
        filename=f"{db_generation.topic.replace(' ', '_')}.mp4",
        media_type="video/mp4"
    )

@app.get("/api/user/{user_id}/history")
async def get_user_history(user_id: str, db: Session = Depends(get_db)):
    """ユーザーの生成履歴"""
    generations = db.query(VideoGeneration).filter(
        VideoGeneration.user_id == user_id
    ).order_by(VideoGeneration.created_at.desc()).limit(20).all()
    
    return {
        "generations": [
            {
                "id": gen.id,
                "topic": gen.topic,
                "style": gen.style,
                "status": gen.status,
                "created_at": gen.created_at.isoformat(),
                "video_url": f"/api/video/download/{gen.id}" if gen.status == "completed" else None
            }
            for gen in generations
        ]
    }

async def process_video_generation(
    generation_id: str,
    topic: str,
    style: str,
    speaker_id: int,
    enable_preview: bool
):
    """バックグラウンドでの動画生成処理"""
    db = SessionLocal()
    try:
        # ステータスを処理中に更新
        db_generation = db.query(VideoGeneration).filter(VideoGeneration.id == generation_id).first()
        db_generation.status = "processing"
        db.commit()
        
        # 進行状況をRedisに保存する関数
        def update_progress(progress: int, step: str):
            redis_client.setex(
                f"progress:{generation_id}",
                300,  # 5分で期限切れ
                json.dumps({"progress": progress, "current_step": step})
            )
        
        # 実際の動画生成（進行状況付き）
        update_progress(10, "台本を生成中...")
        
        # 既存の動画生成システムを呼び出し
        video_path = await generator.generate_improved_video(
            topic, style, speaker_id, enable_preview
        )
        
        if video_path:
            # 成功
            db_generation.status = "completed"
            db_generation.video_url = video_path
            db_generation.completed_at = datetime.utcnow()
            update_progress(100, "完了")
        else:
            # 失敗
            db_generation.status = "failed"
            db_generation.error_message = "動画生成に失敗しました"
            update_progress(0, "エラー")
        
        db.commit()
        
    except Exception as e:
        # エラー処理
        db_generation.status = "failed"
        db_generation.error_message = str(e)
        db.commit()
        
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)