import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
import os
import cv2
import numpy as np
import yt_dlp
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 加载环境变量
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

st.set_page_config(page_title="YouTube 视频评价系统 (Xinpianchang Style)", layout="wide")

# --- L1 Scoring Constants ---
POSITIVE_KEYWORDS = ["买", "链接", "多少钱", "想要", "好用", "求", "推荐", "种草", "哪里买", "价格", "想买", "在哪买"]
NEGATIVE_KEYWORDS = ["广告", "骗子", "假", "难看", "贵", "垃圾", "划走", "没用", "差评", "太长", "无聊"]

def get_video_details(youtube, video_ids):
    request = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids)
    )
    response = request.execute()
    return response.get("items", [])

def get_video_comments(youtube, video_id):
    """获取视频评论（前20条）"""
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=20,
            order="relevance"
        )
        response = request.execute()
        comments = [item["snippet"]["topLevelComment"]["snippet"]["textDisplay"] for item in response.get("items", [])]
        return comments
    except Exception:
        return []

def score_comment_sentiment(comments):
    """基于关键词的简单情感打分 (0-20分)"""
    if not comments:
        return 10  # 默认中性分
    
    score = 10
    for comment in comments:
        comment_lower = comment.lower()
        for word in POSITIVE_KEYWORDS:
            if word in comment_lower:
                score += 1
        for word in NEGATIVE_KEYWORDS:
            if word in comment_lower:
                score -= 1
    
    return max(0, min(20, score))

def get_visual_hook_score(video_url):
    """
    通过 OpenCV 计算视频前3秒的视觉钩子分数 (0-40分)
    逻辑：计算前几秒帧间差异平均值
    """
    try:
        ydl_opts = {
            'format': 'best[height<=360]', # 使用低分辨率加快速度
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            url = info['url']
        
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            return 20
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames_to_process = int(fps * 3) if fps > 0 else 90
        
        ret, prev_frame = cap.read()
        if not ret:
            cap.release()
            return 20
        
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        diffs = []
        
        count = 0
        while count < frames_to_process:
            ret, frame = cap.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray, prev_gray)
            diffs.append(np.mean(diff))
            
            prev_gray = gray
            count += 1
            
        cap.release()
        
        if not diffs:
            return 20
            
        avg_diff = np.mean(diffs)
        # 归一化：假设平均像素差异在 0-30 之间映射到 0-40 分
        score = min(40, (avg_diff / 30) * 40)
        return round(score, 1)
    except Exception:
        return 20

def calculate_l1_score(view_count, like_count, comment_count, sentiment_score, visual_hook_score):
    """L1 综合评分逻辑"""
    # 1. 互动势能 (40%): 权重调整为 (点赞/播放)*200 + (评论/播放)*800
    like_rate = (like_count / view_count) if view_count > 0 else 0
    comment_rate = (comment_count / view_count) if view_count > 0 else 0
    
    engagement_potential = (like_rate * 200 + comment_rate * 800)
    engagement_potential = min(40, engagement_potential)
    
    # 2. 视觉钩子 (40%): 已传入 (0-40)
    # 3. 评论情感 (20%): 已传入 (0-20)
    
    total_score = engagement_potential + visual_hook_score + sentiment_score
    return round(total_score, 1), round(engagement_potential, 1)

def search_videos(query, api_key, proxy, max_results, enable_hook, order="relevance", duration="any", published_after=None, definition="any"):
    if not api_key:
        st.error("请输入有效的 API Key")
        return None
    
    if proxy:
        os.environ["HTTP_PROXY"] = proxy
        os.environ["HTTPS_PROXY"] = proxy
    
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        
        search_params = {
            "q": query,
            "part": "id,snippet",
            "maxResults": max_results,
            "type": "video",
            "order": order,
            "videoDuration": duration,
            "videoDefinition": definition
        }
        
        if published_after:
            search_params["publishedAfter"] = published_after

        search_request = youtube.search().list(**search_params)
        search_response = search_request.execute()
        
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
        if not video_ids:
            return None
            
        details = get_video_details(youtube, video_ids)
        
        data = []
        progress_bar = st.progress(0, text="正在分析视频...")
        for i, item in enumerate(details):
            stats = item["statistics"]
            snippet = item["snippet"]
            video_id = item["id"]
            
            view_count = int(stats.get("viewCount", 0))
            like_count = int(stats.get("likeCount", 0))
            comment_count = int(stats.get("commentCount", 0))
            
            # 情感打分
            comments = get_video_comments(youtube, video_id)
            sentiment_score = score_comment_sentiment(comments)
            
            # 视觉钩子打分
            visual_score = 20
            if enable_hook:
                progress_bar.progress((i + 0.5) / len(details), text=f"分析视觉钩子: {snippet['title'][:30]}...")
                visual_score = get_visual_hook_score(f"https://www.youtube.com/watch?v={video_id}")
            
            l1_total, engagement_score = calculate_l1_score(
                view_count, like_count, comment_count, sentiment_score, visual_score
            )

            data.append({
                "视频标题": snippet["title"],
                "频道": snippet["channelTitle"],
                "观看量": view_count,
                "互动率 (%)": round(((like_count + comment_count) / view_count * 100), 2) if view_count > 0 else 0,
                "L1 综合分": l1_total,
                "互动势能": engagement_score,
                "评论情感": sentiment_score,
                "视觉钩子": visual_score,
                "链接": f"https://www.youtube.com/watch?v={video_id}",
                "封面": snippet["thumbnails"]["medium"]["url"],
                "发布时间": snippet["publishedAt"],
                "描述": snippet.get("description", "")[:100] + "..."
            })
            progress_bar.progress((i + 1) / len(details), text=f"分析完成: {snippet['title'][:30]}...")
        
        progress_bar.empty()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"连接失败: {str(e)}")
        return None

# --- UI Setup ---

# 侧边栏配置：仅保留核心系统设置
st.sidebar.header("⚙️ 系统配置")
api_key_input = st.sidebar.text_input("YouTube API Key", value=API_KEY or "", type="password")
proxy_input = st.sidebar.text_input("代理设置 (可选)", placeholder="例如: http://127.0.0.1:7890")
max_results = st.sidebar.slider("获取视频数量", 5, 50, 20)
enable_visual_hook = st.sidebar.checkbox("开启视觉钩子分析 (速度较慢)", value=False)

# 主界面搜索区
st.markdown("<h1 style='text-align: center;'>🎬 YouTube 视频评价系统</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>仿新片场风格的专业短视频筛选工具</p>", unsafe_allow_html=True)

# 搜索框居中
col_search_1, col_search_2, col_search_3 = st.columns([1, 2, 1])
with col_search_2:
    search_query = st.text_input("", placeholder="输入关键词搜索 YouTube 视频...", label_visibility="collapsed")
    search_button = st.button("🔍 搜索并评价", use_container_width=True)

# 筛选栏 (Filter Bar)
st.markdown("---")
filter_container = st.container()
with filter_container:
    # 第一行：排序
    sort_options = {
        "综合排序": "relevance",
        "最新发布": "date",
        "播放最多": "viewCount",
        "评价最高": "rating"
    }
    order_sel = st.radio("排序方式", options=list(sort_options.keys()), horizontal=True)
    
    # 第二行：时长
    duration_options = {
        "不限时长": "any",
        "短视频 (<4min)": "short",
        "中等视频 (4-20min)": "medium",
        "长视频 (>20min)": "long"
    }
    duration_sel = st.radio("视频时长", options=list(duration_options.keys()), horizontal=True)

    # 第三行：发布时间
    time_options = {
        "不限时间": None,
        "今天": 1,
        "本周": 7,
        "本月": 30,
        "今年": 365
    }
    time_sel = st.radio("发布时间", options=list(time_options.keys()), horizontal=True)

    # 第四行：清晰度
    definition_options = {
        "全部清晰度": "any",
        "仅高清 (HD)": "high"
    }
    definition_sel = st.radio("清晰度", options=list(definition_options.keys()), horizontal=True)

st.markdown("---")

def get_published_after(days):
    if days is None:
        return None
    dt = datetime.utcnow() - timedelta(days=days)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

# 触发搜索
if search_button:
    published_after = get_published_after(time_options[time_sel])
    df = search_videos(
        search_query, 
        api_key_input,
        proxy_input,
        max_results, 
        enable_visual_hook,
        order=sort_options[order_sel],
        duration=duration_options[duration_sel],
        published_after=published_after,
        definition=definition_options[definition_sel]
    )
    st.session_state['df'] = df

if 'df' in st.session_state and st.session_state['df'] is not None:
    df = st.session_state['df']
    # 始终按 L1 分数排序，除非用户选择了特定的 API 排序
    if order_sel == "综合排序":
        df = df.sort_values(by="L1 综合分", ascending=False).reset_index(drop=True)

    tab1, tab2, tab3 = st.tabs(["🖼️ 视觉画廊", "📋 数据列表", "🧐 深度分析"])

    with tab1:
        # 网格化展示
        cols_per_row = 3
        for i in range(0, len(df), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(df):
                    v = df.iloc[i + j]
                    with cols[j]:
                        # 视频卡片样式
                        st.image(v["封面"], use_column_width=True)
                        st.markdown(f"**{v['视频标题'][:40]}...**")
                        st.caption(f"📺 {v['频道']} | 👁️ {v['观看量']:,}")
                        
                        # L1 分数标签
                        score_color = "green" if v['L1 综合分'] > 70 else "orange" if v['L1 综合分'] > 40 else "red"
                        st.markdown(f"<span style='color:{score_color}; font-weight:bold; font-size:1.2em;'>L1 得分: {v['L1 综合分']}</span>", unsafe_allow_html=True)
                        
                        # 简易指标条
                        st.progress(v['互动势能']/40, text=f"互动: {v['互动势能']}")
                        
                        if st.button("查看详情", key=f"btn_{i+j}"):
                            st.session_state['selected_video_idx'] = i + j
                        
                        st.markdown(f"[去 YouTube 观看]({v['链接']})")
                        st.markdown("<br>", unsafe_allow_html=True)

    with tab2:
        st.dataframe(
            df[["视频标题", "L1 综合分", "互动势能", "评论情感", "视觉钩子", "观看量", "链接"]],
            column_config={
                "L1 综合分": st.column_config.NumberColumn("L1 总分", format="%.1f"),
                "链接": st.column_config.LinkColumn("观看链接")
            },
            use_container_width=True
        )

    with tab3:
        # 深度分析部分
        selected_idx = st.session_state.get('selected_video_idx', 0)
        if selected_idx >= len(df): selected_idx = 0
        
        v_data = df.iloc[selected_idx]
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.image(v_data["封面"], use_column_width=True)
            st.markdown(f"### {v_data['视频标题']}")
            st.info(f"**描述**: {v_data['描述']}")
        
        with c2:
            st.metric("L1 综合得分", f"{v_data['L1 综合分']} / 100")
            st.progress(v_data['互动势能']/40, text=f"互动势能 (Max 40): {v_data['互动势能']}")
            st.progress(v_data['视觉钩子']/40, text=f"视觉钩子 (Max 40): {v_data['视觉钩子']}")
            st.progress(v_data['评论情感']/20, text=f"评论情感 (Max 20): {v_data['评论情感']}")
            
            # 对比图
            st.markdown("#### 指标分布")
            chart_data = pd.DataFrame({
                '指标': ['互动势能', '视觉钩子', '评论情感'],
                '分数': [v_data['互动势能'], v_data['视觉钩子'], v_data['评论情感']],
                '满分': [40, 40, 20]
            })
            st.bar_chart(chart_data.set_index('指标'))
else:
    st.info("💡 请在上方输入关键词并选择筛选条件，然后点击“搜索并评价”。")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tips**:\nL1 评分基于元数据和基础物理特征，是低成本大规模筛选的最佳方案。")
