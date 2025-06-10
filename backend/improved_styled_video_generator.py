import os
import json
import asyncio
import aiohttp
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ImageStyle:
    """画像スタイル設定"""
    name: str
    style_prompt: str
    description: str
    base_settings: dict
    consistency_keywords: List[str]  # スタイル統一のためのキーワード

class ImprovedStyledVideoGenerator:
    def __init__(self, openai_api_key: str, voicevox_url: str = "http://localhost:50021"):
        self.openai_api_key = openai_api_key
        self.voicevox_url = voicevox_url
        self.output_dir = Path("generated_videos")
        self.output_dir.mkdir(exist_ok=True)
        
        # MulmoCastの手法を参考にしたスタイル定義
        self.image_styles = {
            "ghibli": ImageStyle(
                name="ジブリ風",
                # MulmoCastで使用されている詳細なプロンプト構造を参考
                style_prompt="""hand-drawn Studio Ghibli animation style, soft pastel colors, gentle watercolor textures, 
                detailed natural backgrounds, whimsical atmosphere, warm golden lighting, anime cel animation, 
                painterly brushstrokes, nostalgic mood, high detail illustration, cinematic composition""",
                description="スタジオジブリ風の一貫した手描きアニメーションスタイル",
                base_settings={"quality": "hd", "style": "natural"},
                consistency_keywords=["Studio Ghibli style", "hand-drawn animation", "soft lighting", "detailed backgrounds"]
            ),
            "anime": ImageStyle(
                name="現代アニメ風",
                style_prompt="""modern anime art style, clean vector lines, vibrant saturated colors, cel shading,
                detailed character design, sharp clean edges, professional anime illustration, bright lighting,
                consistent character proportions, Japanese animation style""",
                description="統一された現代アニメ・マンガスタイル",
                base_settings={"quality": "hd", "style": "vivid"},
                consistency_keywords=["anime art style", "cel shading", "clean lines", "vibrant colors"]
            ),
            "realistic": ImageStyle(
                name="リアル写真風",
                style_prompt="""photorealistic, professional photography, natural lighting, high resolution,
                detailed textures, realistic materials, sharp focus, natural colors, documentary style,
                commercial photography quality""",
                description="一貫したリアル写真スタイル",
                base_settings={"quality": "hd", "style": "natural"},
                consistency_keywords=["photorealistic", "professional photography", "natural lighting", "high detail"]
            ),
            "watercolor": ImageStyle(
                name="水彩画風",
                style_prompt="""traditional watercolor painting, soft flowing brushstrokes, translucent layers,
                gentle color bleeding, artistic paper texture, hand-painted aesthetic, delicate washes,
                organic fluid shapes, traditional art medium""",
                description="統一された水彩画タッチ",
                base_settings={"quality": "hd", "style": "natural"},
                consistency_keywords=["watercolor painting", "soft brushstrokes", "translucent", "hand-painted"]
            )
        }

    def list_available_styles(self) -> None:
        """利用可能なスタイル一覧を表示"""
        print("🎨 利用可能な画像スタイル:")
        print("=" * 50)
        for key, style in self.image_styles.items():
            print(f"{key:12} | {style.name:12} | {style.description}")
        print("=" * 50)

    async def suggest_topics_from_theme(self, theme: str) -> List[str]:
        """テーマから具体的なお題を提案"""
        prompt = f"""
        以下のテーマに基づいて、ショート動画に適した魅力的なお題を5つ提案してください。
        テーマ: {theme}
        
        【提案の条件】
        1. 「○○ 3選」「○○ top5」「○○あるある」などランキング形式にする
        2. 視聴者が興味を持ちそうな内容にする
        3. 15-30秒で説明できる範囲にする
        4. バズりやすそうなキャッチーなタイトルにする
        5. 実用的で役立つ情報を含む
        
        以下のJSON形式で出力してください：
        {{
            "theme": "{theme}",
            "suggestions": [
                {{
                    "title": "具体的なお題タイトル",
                    "description": "このお題の簡単な説明（なぜ面白いか、役立つか）",
                    "estimated_views": "予想視聴回数（バズりやすさの指標）"
                }},
                {{
                    "title": "具体的なお題タイトル2",
                    "description": "このお題の簡単な説明",
                    "estimated_views": "予想視聴回数"
                }}
            ]
        }}
        
        例（テーマ：ダイエット）：
        - ダイエットで気をつけること 3選
        - ダイエット失敗あるある 5選
        - 痩せやすい人の特徴 top3
        - ダイエット中に食べていいもの 3選
        - リバウンドしやすい人の特徴 3選
        """
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8  # 創造性を重視
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    result = await response.json()
                    
                    if "error" in result:
                        print(f"OpenAI APIエラー: {result['error']}")
                        return []
                    
                    suggestion_text = result["choices"][0]["message"]["content"]
                    
                    try:
                        if "```json" in suggestion_text:
                            json_start = suggestion_text.find("```json") + 7
                            json_end = suggestion_text.find("```", json_start)
                            json_text = suggestion_text[json_start:json_end].strip()
                        else:
                            json_start = suggestion_text.find("{")
                            json_end = suggestion_text.rfind("}") + 1
                            json_text = suggestion_text[json_start:json_end]
                        
                        suggestions_data = json.loads(json_text)
                        return suggestions_data["suggestions"]
                        
                    except json.JSONDecodeError as e:
                        print(f"JSON解析エラー: {e}")
                        print(f"取得したテキスト: {suggestion_text}")
                        return []
                        
        except Exception as e:
            print(f"お題提案生成中にエラー: {e}")
            return []

    def display_topic_suggestions(self, suggestions: List[Dict], theme: str) -> None:
        """お題提案を見やすく表示"""
        print(f"\n💡 テーマ「{theme}」のお題提案:")
        print("=" * 60)
        
        for i, suggestion in enumerate(suggestions, 1):
            title = suggestion.get("title", "タイトル不明")
            description = suggestion.get("description", "説明なし")
            views = suggestion.get("estimated_views", "未予測")
            
            print(f"{i}. 📺 {title}")
            print(f"   💭 {description}")
            print(f"   📊 予想視聴数: {views}")
            print("-" * 60)
        
        print("0. 🔄 別のテーマで提案を生成")
        print("=" * 60)

    async def interactive_topic_selection(self) -> str:
        """インタラクティブなお題選択システム"""
        while True:
            print("\n🎯 お題選択システム")
            print("1. 📝 お題を直接入力")
            print("2. 💡 テーマからお題提案を受ける")
            
            choice = input("選択してください (1 or 2): ")
            
            if choice == "1":
                topic = input("📝 お題を直接入力してください: ")
                if topic.strip():
                    return topic.strip()
                else:
                    print("❌ お題を入力してください。")
                    continue
                    
            elif choice == "2":
                while True:
                    theme = input("💡 大まかなテーマを入力してください (例: ダイエット, 節約, 恋愛): ")
                    
                    if not theme.strip():
                        print("❌ テーマを入力してください。")
                        continue
                    
                    print(f"🤔 テーマ「{theme}」から魅力的なお題を提案中...")
                    suggestions = await self.suggest_topics_from_theme(theme.strip())
                    
                    if not suggestions:
                        print("❌ お題提案の生成に失敗しました。別のテーマを試してください。")
                        continue
                    
                    self.display_topic_suggestions(suggestions, theme)
                    
                    while True:
                        selection = input("お題番号を選択してください (1-5, 0で別テーマ): ")
                        
                        if selection == "0":
                            break  # 別テーマへ
                        
                        try:
                            topic_num = int(selection)
                            if 1 <= topic_num <= len(suggestions):
                                selected_topic = suggestions[topic_num - 1]["title"]
                                print(f"✅ 選択されたお題: 「{selected_topic}」")
                                return selected_topic
                            else:
                                print(f"❌ 1から{len(suggestions)}の番号を入力してください。")
                        except ValueError:
                            print("❌ 有効な番号を入力してください。")
                    
                    if selection == "0":
                        continue  # 外側のループに戻る
            else:
                print("❌ 1 または 2 を入力してください。")

    async def generate_script(self, topic: str, style_name: str) -> Dict:
        """改良版台本生成（絵の説明を除去、順位のみフォーカス）"""
        style = self.image_styles.get(style_name)
        if not style:
            raise ValueError(f"スタイル '{style_name}' が見つかりません")

        prompt = f"""
        以下のお題で{style.name}スタイルのショート動画（15-30秒）の台本を作成してください。
        お題: {topic}
        
        【重要な指示】
        1. 各順位を発表した後に、絵や画像の説明は一切含めないでください
        2. 順位の内容のみを簡潔に説明してください
        3. 「この画像は〜」「絵では〜」などの画像説明は禁止です
        4. 視聴者が聞いて理解できる内容のみを話してください
        
        以下のJSON形式で出力してください：
        {{
            "title": "動画タイトル",
            "style": "{style_name}",
            "scenes": [
                {{
                    "text": "第3位は○○です。理由は〜",
                    "visual_concept": "第3位の内容を表現する視覚的コンセプト（内部処理用）",
                    "duration": 5
                }},
                {{
                    "text": "第2位は○○です。理由は〜",
                    "visual_concept": "第2位の内容を表現する視覚的コンセプト（内部処理用）",
                    "duration": 5
                }},
                {{
                    "text": "第1位は○○です。理由は〜",
                    "visual_concept": "第1位の内容を表現する視覚的コンセプト（内部処理用）",
                    "duration": 5
                }}
            ]
        }}
        
        例：
        - 良い例: "第3位は夜遅くに食事をすることです。深夜の食事は代謝が落ちているため脂肪として蓄積されやすくなります。"
        - 悪い例: "第3位は夜遅くに食事をすることです。この画像では時計が深夜を指している様子が描かれています。"
        """
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o",  # より高品質なモデルを使用
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5  # より一貫性を重視
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data
            ) as response:
                result = await response.json()
                
                if "error" in result:
                    print(f"OpenAI APIエラー: {result['error']}")
                    raise Exception(f"API Error: {result['error']['message']}")
                
                script_text = result["choices"][0]["message"]["content"]
                
                try:
                    if "```json" in script_text:
                        json_start = script_text.find("```json") + 7
                        json_end = script_text.find("```", json_start)
                        json_text = script_text[json_start:json_end].strip()
                    else:
                        json_start = script_text.find("{")
                        json_end = script_text.rfind("}") + 1
                        json_text = script_text[json_start:json_end]
                    
                    script = json.loads(json_text)
                    return script
                except json.JSONDecodeError as e:
                    print(f"JSON解析エラー: {e}")
                    print(f"取得したテキスト: {script_text}")
                    raise

    async def generate_consistent_image(self, visual_concept: str, style_name: str, scene_num: int, character_reference: str = "") -> str:
        """スタイル統一性を重視した画像生成"""
        style = self.image_styles[style_name]
        
        # 統一性のためのベースプロンプト構築
        base_consistency = f"""Consistent {' '.join(style.consistency_keywords)}, 
        maintaining identical art style throughout, same artistic technique, uniform color palette"""
        
        # キャラクター一貫性の追加
        if character_reference:
            character_consistency = f", {character_reference}"
        else:
            character_consistency = ""
        
        # 最終プロンプト構築（MulmoCast手法参考）
        full_prompt = f"""{visual_concept}, {base_consistency}{character_consistency}, {style.style_prompt}"""
        
        # プロンプト長制限
        if len(full_prompt) > 1000:
            full_prompt = f"{visual_concept[:300]}, {base_consistency}, {style.style_prompt[:400]}"
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        # MulmoCastが使用するgpt-image-1相当の設定
        data = {
            "model": "dall-e-3",
            "prompt": full_prompt,
            "size": "1024x1024",
            "quality": style.base_settings["quality"],
            "style": style.base_settings["style"],
            "n": 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=headers,
                    json=data
                ) as response:
                    result = await response.json()
                    
                    if "error" in result:
                        print(f"画像生成エラー: {result['error']['message']}")
                        return self.create_styled_dummy_image(scene_num, visual_concept, style_name)
                    
                    image_url = result["data"][0]["url"]
                    
                    # 画像をダウンロード
                    async with session.get(image_url) as img_response:
                        image_path = self.output_dir / f"{style_name}_consistent_scene_{scene_num}.png"
                        with open(image_path, "wb") as f:
                            f.write(await img_response.read())
                        
                        print(f"✅ {style.name}スタイル画像生成完了: シーン{scene_num + 1}")
                        return str(image_path)
                        
        except Exception as e:
            print(f"画像生成中にエラー: {e}")
            return self.create_styled_dummy_image(scene_num, visual_concept, style_name)

    def create_styled_dummy_image(self, scene_num: int, concept: str, style_name: str) -> str:
        """スタイル統一されたダミー画像を作成"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            style = self.image_styles[style_name]
            
            # スタイル別カラーパレット
            color_schemes = {
                "ghibli": {"bg": "#E8F4FD", "text": "#2E4F3D", "accent": "#7FB069"},
                "anime": {"bg": "#FFF0F8", "text": "#2D3748", "accent": "#FF6B9D"},
                "realistic": {"bg": "#F7FAFC", "text": "#1A202C", "accent": "#4A5568"},
                "watercolor": {"bg": "#F0F8F8", "text": "#2C5F5F", "accent": "#4A90A4"}
            }
            
            colors = color_schemes.get(style_name, {"bg": "#F5F5F5", "text": "#333333", "accent": "#666666"})
            
            img = Image.new('RGB', (1080, 1920), color=colors["bg"])
            draw = ImageDraw.Draw(img)
            
            # スタイル名とシーン情報
            title_text = f"【{style.name}】"
            scene_text = f"シーン {scene_num + 1}"
            concept_text = concept[:100] + "..." if len(concept) > 100 else concept
            
            try:
                title_font = ImageFont.truetype("msgothic.ttc", 64)
                scene_font = ImageFont.truetype("msgothic.ttc", 48)
                concept_font = ImageFont.truetype("msgothic.ttc", 36)
            except:
                title_font = ImageFont.load_default()
                scene_font = ImageFont.load_default()
                concept_font = ImageFont.load_default()
            
            # タイトル描画
            title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
            title_x = (1080 - (title_bbox[2] - title_bbox[0])) // 2
            draw.text((title_x, 300), title_text, fill=colors["accent"], font=title_font)
            
            # シーン番号描画
            scene_bbox = draw.textbbox((0, 0), scene_text, font=scene_font)
            scene_x = (1080 - (scene_bbox[2] - scene_bbox[0])) // 2
            draw.text((scene_x, 500), scene_text, fill=colors["text"], font=scene_font)
            
            # コンセプト描画
            concept_bbox = draw.textbbox((0, 0), concept_text, font=concept_font)
            concept_x = (1080 - (concept_bbox[2] - concept_bbox[0])) // 2
            draw.text((concept_x, 700), concept_text, fill=colors["text"], font=concept_font)
            
            image_path = self.output_dir / f"{style_name}_consistent_scene_{scene_num}.png"
            img.save(image_path)
            print(f"📸 {style.name}スタイルダミー画像作成: {image_path}")
            return str(image_path)
            
        except ImportError:
            print("PILがインストールされていません。基本ダミーファイルを作成します。")
            image_path = self.output_dir / f"{style_name}_consistent_scene_{scene_num}.txt"
            with open(image_path, "w", encoding="utf-8") as f:
                f.write(f"スタイル: {style_name}\nシーン: {scene_num + 1}\nコンセプト: {concept}")
            return str(image_path)

    async def generate_audio(self, text: str, scene_num: int, speaker_id: int = 1) -> str:
        """VOICEVOXで音声を生成"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.voicevox_url}/audio_query",
                    params={"text": text, "speaker": speaker_id}
                ) as response:
                    if response.status != 200:
                        print(f"音声クエリ取得失敗: {response.status}")
                        return ""
                    audio_query = await response.json()
                
                async with session.post(
                    f"{self.voicevox_url}/synthesis",
                    params={"speaker": speaker_id},
                    json=audio_query
                ) as response:
                    if response.status != 200:
                        print(f"音声合成失敗: {response.status}")
                        return ""
                    
                    audio_data = await response.read()
                    audio_path = self.output_dir / f"consistent_scene_{scene_num}.wav"
                    with open(audio_path, "wb") as f:
                        f.write(audio_data)
                    return str(audio_path)
                    
        except Exception as e:
            print(f"音声生成エラー: {e}")
            return ""

    def create_title_image(self, title: str, style_name: str) -> str:
        """タイトル画面の画像を作成"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            style = self.image_styles[style_name]
            
            # スタイル別デザイン設定
            design_schemes = {
                "ghibli": {
                    "bg_color": "#2E4F3D",
                    "text_color": "#F0F8F0", 
                    "accent_color": "#7FB069",
                    "gradient": True
                },
                "anime": {
                    "bg_color": "#1A1A2E",
                    "text_color": "#FFFFFF",
                    "accent_color": "#FF6B9D",
                    "gradient": True
                },
                "realistic": {
                    "bg_color": "#000000",
                    "text_color": "#FFFFFF",
                    "accent_color": "#4A90A4",
                    "gradient": False
                },
                "watercolor": {
                    "bg_color": "#2C3E50",
                    "text_color": "#ECF0F1",
                    "accent_color": "#3498DB",
                    "gradient": True
                }
            }
            
            design = design_schemes.get(style_name, design_schemes["realistic"])
            
            # 1080x1920の縦型画像を作成
            img = Image.new('RGB', (1080, 1920), color=design["bg_color"])
            draw = ImageDraw.Draw(img)
            
            # グラデーション効果（簡易版）
            if design["gradient"]:
                for y in range(1920):
                    alpha = y / 1920
                    # 上から下に向かって少し明るくなるグラデーション
                    r = int(int(design["bg_color"][1:3], 16) * (1 + alpha * 0.2))
                    g = int(int(design["bg_color"][3:5], 16) * (1 + alpha * 0.2))
                    b = int(int(design["bg_color"][5:7], 16) * (1 + alpha * 0.2))
                    r, g, b = min(255, r), min(255, g), min(255, b)
                    color = f"#{r:02x}{g:02x}{b:02x}"
                    draw.line([(0, y), (1080, y)], fill=color)
            
            # フォント設定
            try:
                # 日本語フォントを試す
                title_font = ImageFont.truetype("msgothic.ttc", 72)
                subtitle_font = ImageFont.truetype("msgothic.ttc", 48)
            except:
                try:
                    # 英語フォントを試す
                    title_font = ImageFont.truetype("arial.ttf", 72)
                    subtitle_font = ImageFont.truetype("arial.ttf", 48)
                except:
                    # デフォルトフォント
                    title_font = ImageFont.load_default()
                    subtitle_font = ImageFont.load_default()
            
            # タイトルテキストの処理
            title_text = title
            
            # アクセントライン描画
            accent_y = 800
            draw.rectangle([(200, accent_y), (880, accent_y + 8)], fill=design["accent_color"])
            
            # タイトルテキストの描画
            title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_height = title_bbox[3] - title_bbox[1]
            
            # 長いタイトルの場合は改行
            if title_width > 900:
                # 簡易的な改行処理
                words = title_text.split()
                if len(words) > 1:
                    mid = len(words) // 2
                    line1 = " ".join(words[:mid])
                    line2 = " ".join(words[mid:])
                    
                    # 1行目
                    line1_bbox = draw.textbbox((0, 0), line1, font=title_font)
                    line1_width = line1_bbox[2] - line1_bbox[0]
                    line1_x = (1080 - line1_width) // 2
                    draw.text((line1_x, 900), line1, fill=design["text_color"], font=title_font)
                    
                    # 2行目
                    line2_bbox = draw.textbbox((0, 0), line2, font=title_font)
                    line2_width = line2_bbox[2] - line2_bbox[0]
                    line2_x = (1080 - line2_width) // 2
                    draw.text((line2_x, 1000), line2, fill=design["text_color"], font=title_font)
                else:
                    # 1つの単語の場合はそのまま
                    title_x = (1080 - title_width) // 2
                    draw.text((title_x, 950), title_text, fill=design["text_color"], font=title_font)
            else:
                # 1行で収まる場合
                title_x = (1080 - title_width) // 2
                draw.text((title_x, 950), title_text, fill=design["text_color"], font=title_font)
            
            # スタイル表示
            style_text = f"Style: {style.name}"
            style_bbox = draw.textbbox((0, 0), style_text, font=subtitle_font)
            style_width = style_bbox[2] - style_bbox[0]
            style_x = (1080 - style_width) // 2
            draw.text((style_x, 1200), style_text, fill=design["accent_color"], font=subtitle_font)
            
            # 装飾要素
            # 上部の装飾線
            draw.rectangle([(340, 600), (740, 608)], fill=design["accent_color"])
            # 下部の装飾線  
            draw.rectangle([(340, 1400), (740, 1408)], fill=design["accent_color"])
            
            # 角の装飾
            corner_size = 50
            # 左上
            draw.rectangle([(100, 100), (100 + corner_size, 108)], fill=design["accent_color"])
            draw.rectangle([(100, 100), (108, 100 + corner_size)], fill=design["accent_color"])
            # 右上
            draw.rectangle([(980 - corner_size, 100), (980, 108)], fill=design["accent_color"])
            draw.rectangle([(972, 100), (980, 100 + corner_size)], fill=design["accent_color"])
            # 左下
            draw.rectangle([(100, 1812), (100 + corner_size, 1820)], fill=design["accent_color"])
            draw.rectangle([(100, 1820 - corner_size), (108, 1820)], fill=design["accent_color"])
            # 右下
            draw.rectangle([(980 - corner_size, 1812), (980, 1820)], fill=design["accent_color"])
            draw.rectangle([(972, 1820 - corner_size), (980, 1820)], fill=design["accent_color"])
            
            title_image_path = self.output_dir / f"title_{style_name}.png"
            img.save(title_image_path)
            print(f"📺 タイトル画面作成完了: {title_image_path}")
            return str(title_image_path)
            
        except ImportError:
            print("❌ PILがインストールされていません。pip install Pillow を実行してください。")
            # 基本的なテキストファイルを作成
            title_image_path = self.output_dir / f"title_{style_name}.txt"
            with open(title_image_path, "w", encoding="utf-8") as f:
                f.write(f"タイトル: {title}\nスタイル: {style_name}")
            return str(title_image_path)
        except Exception as e:
            print(f"タイトル画像作成中にエラー: {e}")
            title_image_path = self.output_dir / f"title_{style_name}.txt"
            with open(title_image_path, "w", encoding="utf-8") as f:
                f.write(f"タイトル: {title}\nスタイル: {style_name}")
            return str(title_image_path)

    async def generate_title_audio(self, title: str, speaker_id: int = 1) -> str:
        """タイトル読み上げ音声を生成"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.voicevox_url}/audio_query",
                    params={"text": title, "speaker": speaker_id}
                ) as response:
                    if response.status != 200:
                        print(f"タイトル音声クエリ取得失敗: {response.status}")
                        return ""
                    audio_query = await response.json()
                
                # 少し間を開けるために速度を調整
                audio_query["speedScale"] = 0.9  # 少しゆっくり読む
                
                async with session.post(
                    f"{self.voicevox_url}/synthesis",
                    params={"speaker": speaker_id},
                    json=audio_query
                ) as response:
                    if response.status != 200:
                        print(f"タイトル音声合成失敗: {response.status}")
                        return ""
                    
                    audio_data = await response.read()
                    title_audio_path = self.output_dir / "title_audio.wav"
                    with open(title_audio_path, "wb") as f:
                        f.write(audio_data)
                    
                    print(f"🎵 タイトル音声生成完了: {title_audio_path}")
                    return str(title_audio_path)
                    
        except Exception as e:
            print(f"タイトル音声生成エラー: {e}")
            return ""

    def create_video(self, script: Dict, image_paths: List[str], audio_paths: List[str], title_image_path: str = "", title_audio_path: str = "") -> str:
        """タイトル付きFFmpeg動画生成"""
        style_name = script.get('style', 'default')
        output_path = self.output_dir / f"{script['title'].replace(' ', '_')}_{style_name}_with_title.mp4"
        
        temp_videos = []
        
        try:
            # タイトルシーンの作成
            if title_image_path and title_audio_path:
                title_temp_video = self.output_dir / f"temp_title_{style_name}.mp4"
                temp_videos.append(title_temp_video)
                
                # タイトル音声の長さを取得
                try:
                    duration_cmd = [
                        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", title_audio_path
                    ]
                    title_duration = float(subprocess.check_output(duration_cmd).decode().strip())
                    # タイトル表示時間を少し長めに（音声＋0.5秒）
                    title_duration += 0.5
                except:
                    title_duration = 3  # デフォルト3秒
                
                # タイトル動画作成
                title_ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", title_image_path,
                    "-i", title_audio_path,
                    "-c:v", "libx264", "-t", str(title_duration),
                    "-pix_fmt", "yuv420p",
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                    "-c:a", "aac", "-b:a", "128k",
                    "-preset", "medium",
                    str(title_temp_video)
                ]
                
                try:
                    subprocess.run(title_ffmpeg_cmd, check=True, capture_output=True)
                    print(f"📺 タイトルシーン動画作成完了")
                except subprocess.CalledProcessError as e:
                    print(f"❌ タイトルシーン動画作成失敗: {e}")
                    temp_videos.remove(title_temp_video)
            
            # メインコンテンツシーンの作成
            for i, (scene, img_path, audio_path) in enumerate(zip(script["scenes"], image_paths, audio_paths)):
                if not img_path or not audio_path:
                    print(f"シーン{i+1}をスキップ: 素材が不完全")
                    continue
                    
                temp_video = self.output_dir / f"temp_improved_{style_name}_scene_{i}.mp4"
                temp_videos.append(temp_video)
                
                # 音声の長さを取得
                try:
                    duration_cmd = [
                        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", audio_path
                    ]
                    duration = float(subprocess.check_output(duration_cmd).decode().strip())
                except:
                    duration = 5
                
                # より高品質な動画作成設定
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", img_path,
                    "-i", audio_path,
                    "-c:v", "libx264", "-t", str(duration),
                    "-pix_fmt", "yuv420p",
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                    "-c:a", "aac", "-b:a", "128k",
                    "-preset", "medium",  # 品質重視
                    str(temp_video)
                ]
                
                try:
                    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                    print(f"✅ シーン{i+1}動画作成完了（{style_name}スタイル）")
                except subprocess.CalledProcessError as e:
                    print(f"❌ シーン{i+1}動画作成失敗: {e}")
                    temp_videos.remove(temp_video)
                    continue
            
            if not temp_videos:
                return ""
            
            # 全動画結合（タイトル→コンテンツの順）
            if len(temp_videos) > 1:
                concat_file = self.output_dir / f"concat_with_title_{style_name}.txt"
                with open(concat_file, "w", encoding='utf-8') as f:
                    for video in temp_videos:
                        video_path = str(video.absolute()).replace('\\', '/')
                        f.write(f"file '{video_path}'\n")
                
                concat_cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_file),
                    "-c", "copy",
                    str(output_path)
                ]
                
                try:
                    subprocess.run(concat_cmd, check=True, capture_output=True, text=False)
                    print(f"🎬 タイトル付き動画結合成功（{style_name}スタイル）")
                except subprocess.CalledProcessError:
                    print("代替方法で動画結合中...")
                    # 最初の動画のみ使用
                    temp_videos[0].rename(output_path)
                
                if concat_file.exists():
                    concat_file.unlink()
            else:
                # 1つの動画のみの場合
                temp_videos[0].rename(output_path)
            
            return str(output_path)
            
        finally:
            for temp_video in temp_videos:
                if temp_video.exists():
                    temp_video.unlink()

    async def generate_improved_video(self, topic: str, style_name: str, speaker_id: int = 1, enable_preview: bool = False) -> str:
        """改良版メイン処理：タイトル画面付きスタイル統一動画"""
        if style_name not in self.image_styles:
            raise ValueError(f"スタイル '{style_name}' が見つかりません。利用可能: {list(self.image_styles.keys())}")
        
        style = self.image_styles[style_name]
        print(f"🎬 お題「{topic}」を{style.name}スタイルで動画生成を開始...")
        
        # 1. 台本生成
        print(f"📝 改良版台本生成中（絵の説明なし）...")
        script = await self.generate_script(topic, style_name)
        print(f"✅ 台本生成完了: {script['title']}")
        
        # プレビュー機能（将来のWeb版用）
        if enable_preview:
            print("\n📋 生成された台本:")
            print("=" * 50)
            print(f"📺 タイトル: {script['title']}")
            print("-" * 50)
            for i, scene in enumerate(script["scenes"]):
                print(f"シーン{i+1}: {scene['text']}")
            print("=" * 50)
            
            # 実際の確認はコマンドライン版では省略
            confirmation = input("この台本で動画を生成しますか？ (y/n): ")
            if confirmation.lower() != 'y':
                print("動画生成をキャンセルしました。")
                return ""
        
        # 2. タイトル画面とタイトル音声を生成
        print(f"📺 {style.name}スタイルのタイトル画面を作成中...")
        title_image_path = self.create_title_image(script['title'], style_name)
        
        print(f"🎵 タイトル音声を生成中...")
        title_audio_path = await self.generate_title_audio(script['title'], speaker_id)
        
        # 3. スタイル統一画像生成
        print(f"🎨 {style.name}スタイル統一画像生成中...")
        
        # キャラクター一貫性のための参照情報
        character_ref = "same consistent character design throughout all scenes" if "人" in topic else ""
        
        tasks = []
        for i, scene in enumerate(script["scenes"]):
            tasks.append(self.generate_consistent_image(scene["visual_concept"], style_name, i, character_ref))
            tasks.append(self.generate_audio(scene["text"], i, speaker_id))
        
        results = await asyncio.gather(*tasks)
        
        # 結果を分離
        image_paths = results[::2]  # 偶数インデックス（画像）
        audio_paths = results[1::2]  # 奇数インデックス（音声）
        
        print("🎬 タイトル付き最終動画作成中...")
        video_path = self.create_video(script, image_paths, audio_paths, title_image_path, title_audio_path)
        
        if video_path:
            print(f"🎉 {style.name}スタイル統一動画生成完了!")
            print(f"📁 ファイル: {video_path}")
            print("✨ 追加された要素:")
            print(f"  📺 タイトル画面: {script['title']}")
            print(f"  🎵 タイトル音声読み上げ")
            print(f"  🎨 {style.name}スタイル統一画像")
        else:
            print("❌ 動画生成失敗")
        
        return video_path

# 使用例（お題選択システム統合版）
async def main():
    OPENAI_API_KEY = "your-openai-api-key-here"  # プレースホルダーに戻す
    VOICEVOX_URL = "http://localhost:50021"
    
    generator = ImprovedStyledVideoGenerator(OPENAI_API_KEY, VOICEVOX_URL)
    
    print("🎬 改良版ショート動画生成システム")
    print("✨ 新機能: テーマからお題提案、絵の説明なし、スタイル統一強化")
    print("=" * 60)
    
    # インタラクティブなお題選択
    topic = await generator.interactive_topic_selection()
    
    # 利用可能なスタイルを表示
    print("\n" + "=" * 60)
    generator.list_available_styles()
    
    print("\n🎨 画像スタイルを選択してください:")
    style_input = input("スタイル名を入力 (ghibli, anime, realistic, watercolor): ")
    
    print("\n🎤 音声の話者を選択してください:")
    print("1: ずんだもん, 2: 四国めたん, 3: 春日部つむぎ, 8: 青山龍星")
    speaker_id = int(input("話者ID (1-8): ") or "1")
    
    # プレビュー機能の有効化確認
    preview_choice = input("\n📋 台本プレビュー機能を使用しますか？ (y/n): ")
    enable_preview = preview_choice.lower() == 'y'
    
    try:
        video_path = await generator.generate_improved_video(topic, style_input, speaker_id, enable_preview)
        
        if video_path:
            print(f"\n🎉 改良版動画生成完了!")
            print(f"📁 ファイル: {video_path}")
            print("📂 generated_videosフォルダを確認してください！")
            print("\n✨ 搭載機能:")
            print("- 💡 テーマからお題自動提案")
            print("- 📝 絵の説明除去")
            print("- 🎨 スタイル統一強化")
            print("- 📋 台本プレビュー機能")
            print("- 🎬 高品質動画エンコーディング")
        else:
            print("\n❌ 動画生成に失敗しました")
            
    except ValueError as e:
        print(f"\n❌ エラー: {e}")
        generator.list_available_styles()

# 個別テスト用：お題提案機能のみテスト
async def test_topic_suggestion():
    """お題提案機能のテスト"""
    OPENAI_API_KEY = "your-openai-api-key-here"  # プレースホルダーに戻す
    VOICEVOX_URL = "http://localhost:50021"
    
    generator = ImprovedStyledVideoGenerator(OPENAI_API_KEY, VOICEVOX_URL)
    
    print("💡 お題提案機能テスト")
    theme = input("テーマを入力してください: ")
    
    suggestions = await generator.suggest_topics_from_theme(theme)
    generator.display_topic_suggestions(suggestions, theme)

if __name__ == "__main__":
    # メイン実行
    asyncio.run(main())
    
    # お題提案のみテストしたい場合は以下のコメントアウトを外す
    # asyncio.run(test_topic_suggestion())