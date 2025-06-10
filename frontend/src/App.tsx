// App.tsx - メインアプリケーションコンポーネント
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// 型定義
interface TopicSuggestion {
  title: string;
  description: string;
  estimated_views: string;
}

interface Style {
  id: string;
  name: string;
  description: string;
  consistency_keywords: string[];
}

interface VideoGenerationRequest {
  topic: string;
  style: string;
  speaker_id: number;
  enable_preview: boolean;
  user_id?: string;
}

interface VideoStatus {
  generation_id: string;
  status: string;
  progress: number;
  current_step: string;
  video_url?: string;
  error_message?: string;
}

interface ScriptPreview {
  title: string;
  style: string;
  scenes: Array<{
    text: string;
    visual_concept: string;
    duration: number;
  }>;
}

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const App: React.FC = () => {
  // State管理
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [topicMethod, setTopicMethod] = useState<'theme' | 'direct'>('theme');
  const [theme, setTheme] = useState<string>('');
  const [directTopic, setDirectTopic] = useState<string>('');
  const [selectedTopic, setSelectedTopic] = useState<string>('');
  const [suggestions, setSuggestions] = useState<TopicSuggestion[]>([]);
  const [styles, setStyles] = useState<Style[]>([]);
  const [selectedStyle, setSelectedStyle] = useState<string>('');
  const [speakerId, setSpeakerId] = useState<number>(1);
  const [enablePreview, setEnablePreview] = useState<boolean>(false);
  const [scriptPreview, setScriptPreview] = useState<ScriptPreview | null>(null);
  const [generationId, setGenerationId] = useState<string>('');
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  // 初期化: スタイル一覧を取得
  useEffect(() => {
    fetchStyles();
  }, []);

  // API呼び出し関数
  const fetchStyles = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/styles`);
      setStyles(response.data.styles);
    } catch (error) {
      console.error('スタイル取得エラー:', error);
      setError('スタイル情報の取得に失敗しました');
    }
  };

  const generateSuggestions = async () => {
    if (!theme.trim()) {
      setError('テーマを入力してください');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/topics/suggest`, {
        theme: theme.trim()
      });
      setSuggestions(response.data);
    } catch (error) {
      console.error('お題提案エラー:', error);
      setError('お題提案の生成に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const previewScript = async () => {
    const topic = topicMethod === 'theme' ? selectedTopic : directTopic;
    
    if (!topic || !selectedStyle) {
      setError('お題とスタイルを選択してください');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${API_BASE_URL}/api/script/preview`, {
        topic,
        style: selectedStyle,
        speaker_id: speakerId,
        enable_preview: true
      });
      setScriptPreview(response.data);
      setCurrentStep(4); // プレビューステップに移動
    } catch (error) {
      console.error('台本プレビューエラー:', error);
      setError('台本プレビューの生成に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const generateVideo = async (usePreviewedScript: boolean = false) => {
    const topic = usePreviewedScript && scriptPreview ? 
      scriptPreview.title : 
      (topicMethod === 'theme' ? selectedTopic : directTopic);
    
    if (!topic || !selectedStyle) {
      setError('お題とスタイルを選択してください');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${API_BASE_URL}/api/video/generate`, {
        topic,
        style: selectedStyle,
        speaker_id: speakerId,
        enable_preview: false,
        user_id: 'demo_user' // 実際はユーザー認証から取得
      });
      
      setGenerationId(response.data.generation_id);
      setCurrentStep(5); // 進行状況ステップに移動
      pollVideoStatus(response.data.generation_id);
    } catch (error) {
      console.error('動画生成エラー:', error);
      setError('動画生成の開始に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const pollVideoStatus = async (id: string) => {
    const poll = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/video/status/${id}`);
        setVideoStatus(response.data);
        
        if (response.data.status === 'completed') {
          setCurrentStep(6); // 完了ステップに移動
        } else if (response.data.status === 'failed') {
          setError(response.data.error_message || '動画生成に失敗しました');
        } else {
          // 処理中の場合は3秒後に再度確認
          setTimeout(poll, 3000);
        }
      } catch (error) {
        console.error('ステータス確認エラー:', error);
        setError('進行状況の確認に失敗しました');
      }
    };
    
    poll();
  };

  const downloadVideo = () => {
    if (generationId) {
      window.open(`${API_BASE_URL}/api/video/download/${generationId}`, '_blank');
    }
  };

  const resetForm = () => {
    setCurrentStep(1);
    setTheme('');
    setDirectTopic('');
    setSelectedTopic('');
    setSuggestions([]);
    setSelectedStyle('');
    setScriptPreview(null);
    setGenerationId('');
    setVideoStatus(null);
    setError('');
  };

  // レンダリング関数
  const renderStepIndicator = () => (
    <div className="step-indicator">
      <div className="steps">
        {[
          '💡 お題選択',
          '🎨 スタイル選択', 
          '🎤 音声設定',
          '📋 プレビュー',
          '🔄 生成中',
          '🎉 完了'
        ].map((step, index) => (
          <div 
            key={index}
            className={`step ${currentStep > index ? 'completed' : ''} ${currentStep === index + 1 ? 'active' : ''}`}
          >
            <div className="step-number">{index + 1}</div>
            <div className="step-label">{step}</div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderTopicSelection = () => (
    <div className="step-content">
      <h2>💡 お題を選択</h2>
      
      <div className="input-group">
        <label>方法を選択してください</label>
        <select 
          value={topicMethod} 
          onChange={(e) => setTopicMethod(e.target.value as 'theme' | 'direct')}
        >
          <option value="theme">テーマから提案を受ける</option>
          <option value="direct">直接入力する</option>
        </select>
      </div>

      {topicMethod === 'theme' ? (
        <div>
          <div className="input-group">
            <label>大まかなテーマを入力</label>
            <input
              type="text"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder="例: ダイエット, 節約, 恋愛"
            />
          </div>
          
          <button 
            className="btn primary"
            onClick={generateSuggestions}
            disabled={loading || !theme.trim()}
          >
            {loading ? '生成中...' : '💡 お題を提案してもらう'}
          </button>

          {suggestions.length > 0 && (
            <div className="suggestions-grid">
              {suggestions.map((suggestion, index) => (
                <div
                  key={index}
                  className={`suggestion-card ${selectedTopic === suggestion.title ? 'selected' : ''}`}
                  onClick={() => setSelectedTopic(suggestion.title)}
                >
                  <h4>📺 {suggestion.title}</h4>
                  <p>💭 {suggestion.description}</p>
                  <p>📊 予想視聴数: {suggestion.estimated_views}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="input-group">
          <label>お題を直接入力</label>
          <input
            type="text"
            value={directTopic}
            onChange={(e) => setDirectTopic(e.target.value)}
            placeholder="例: 太りやすい人の特徴 3選"
          />
        </div>
      )}

      <div className="step-actions">
        <button 
          className="btn primary"
          onClick={() => setCurrentStep(2)}
          disabled={topicMethod === 'theme' ? !selectedTopic : !directTopic.trim()}
        >
          次へ：スタイル選択 →
        </button>
      </div>
    </div>
  );

  const renderStyleSelection = () => (
    <div className="step-content">
      <h2>🎨 画像スタイルを選択</h2>
      
      <div className="styles-grid">
        {styles.map((style) => (
          <div
            key={style.id}
            className={`style-card ${selectedStyle === style.id ? 'selected' : ''}`}
            onClick={() => setSelectedStyle(style.id)}
          >
            <div className="style-icon">
              {style.id === 'ghibli' && '🌱'}
              {style.id === 'anime' && '⚡'}
              {style.id === 'realistic' && '📷'}
              {style.id === 'watercolor' && '🎨'}
            </div>
            <h3>{style.name}</h3>
            <p>{style.description}</p>
          </div>
        ))}
      </div>

      <div className="step-actions">
        <button className="btn secondary" onClick={() => setCurrentStep(1)}>
          ← 戻る
        </button>
        <button 
          className="btn primary"
          onClick={() => setCurrentStep(3)}
          disabled={!selectedStyle}
        >
          次へ：音声設定 →
        </button>
      </div>
    </div>
  );

  const renderAudioSettings = () => (
    <div className="step-content">
      <h2>🎤 音声設定</h2>
      
      <div className="input-group">
        <label>話者を選択</label>
        <select value={speakerId} onChange={(e) => setSpeakerId(Number(e.target.value))}>
          <option value={1}>ずんだもん</option>
          <option value={2}>四国めたん</option>
          <option value={3}>春日部つむぎ</option>
          <option value={8}>青山龍星</option>
        </select>
      </div>

      <div className="input-group">
        <label>
          <input
            type="checkbox"
            checked={enablePreview}
            onChange={(e) => setEnablePreview(e.target.checked)}
          />
          台本プレビューを表示する
        </label>
      </div>

      <div className="step-actions">
        <button className="btn secondary" onClick={() => setCurrentStep(2)}>
          ← 戻る
        </button>
        
        {enablePreview ? (
          <button 
            className="btn primary"
            onClick={previewScript}
            disabled={loading}
          >
            {loading ? '生成中...' : '📋 台本をプレビュー →'}
          </button>
        ) : (
          <button 
            className="btn primary"
            onClick={() => generateVideo(false)}
            disabled={loading}
          >
            {loading ? '生成中...' : '🎬 動画を生成 →'}
          </button>
        )}
      </div>
    </div>
  );

  const renderScriptPreview = () => (
    <div className="step-content">
      <h2>📋 生成された台本</h2>
      
      {scriptPreview && (
        <div className="script-preview">
          <h3>📺 タイトル: {scriptPreview.title}</h3>
          <div className="script-scenes">
            {scriptPreview.scenes.map((scene, index) => (
              <div key={index} className="scene">
                <h4>シーン{index + 1}:</h4>
                <p>{scene.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="step-actions">
        <button className="btn secondary" onClick={() => setCurrentStep(3)}>
          ← 戻る
        </button>
        <button 
          className="btn secondary"
          onClick={previewScript}
          disabled={loading}
        >
          🔄 台本を再生成
        </button>
        <button 
          className="btn primary"
          onClick={() => generateVideo(true)}
          disabled={loading}
        >
          {loading ?