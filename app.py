import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

st.set_page_config(page_title="YouTube 视频评价系统 (广告专版)", layout="wide")

st.title("🚀 YouTube 视频评价系统")
st.markdown("---")

# 侧边栏配置
st.sidebar.header("配置与搜索")
api_key_input = st.sidebar.text_input("YouTube API Key", value=API_KEY or "", type="password")
proxy_input = st.sidebar.text_input("代理设置 (可选)", placeholder="例如: http://127.0.0.1:7890")
search_query = st.sidebar.text_input("搜索关键词 (如: 美妆、数码测评)", value="Shorts")
max_results = st.sidebar.slider("获取视频数量", 5, 50, 20)

def get_video_details(youtube, video_ids):
    request = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids)
    )
    response = request.execute()
    return response.get("items", [])

def search_videos(query, max_results):
    if not api_key_input:
        st.error("请输入有效的 API Key")
        return None
    
    # 配置代理逻辑
    if proxy_input:
        os.environ["HTTP_PROXY"] = proxy_input
        os.environ["HTTPS_PROXY"] = proxy_input
    
    try:
        youtube = build("youtube", "v3", developerKey=api_key_input)
        
        # 搜索视频
        search_request = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=max_results,
            type="video",
            videoDuration="short"  # 筛选短视频
        )
        search_response = search_request.execute()
        
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
        if not video_ids:
            return None
            
        details = get_video_details(youtube, video_ids)
        
        data = []
        for item in details:
            stats = item["statistics"]
            snippet = item["snippet"]
            
            view_count = int(stats.get("viewCount", 0))
            like_count = int(stats.get("likeCount", 0))
            comment_count = int(stats.get("commentCount", 0))
            
            # 核心评价算法：互动率
            engagement = ((like_count + comment_count) / view_count * 100) if view_count > 0 else 0

            # --- 新增：创意评分占位 ---
            data.append({
                "视频标题": snippet["title"],
                "频道": snippet["channelTitle"],
                "观看量": view_count,
                "互动率 (%)": round(engagement, 2),
                "创意分": 8.0,
                "制作分": 8.0,
                "行业匹配": 8.5,
                "节奏分": 8.0,
                "综合得分": 8.1,
                "一句话理由": "内容极具张力，视觉风格独特。",
                "关键元素": "快剪, 高饱和, 故事型",
                "链接": f"https://www.youtube.com/watch?v={item['id']}",
                "描述": snippet.get("description", "")[:100] + "..."
            })
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"连接失败: {str(e)}")
        if "10060" in str(e):
            st.warning("💡 检测到网络超时。如果您在中国大陆使用，请在左侧侧边栏配置您的代理服务器地址（如 http://127.0.0.1:7890）。")
        return None

if st.sidebar.button("开始筛选"):
    with st.spinner("正在抓取并评价视频..."):
        df = search_videos(search_query, max_results)
        st.session_state['df'] = df

if 'df' in st.session_state and st.session_state['df'] is not None:
    df = st.session_state['df']
    
    # 计算综合评分
    df["综合评分"] = (
        df["互动率 (%)"] * 0.3 + 
        df["创意分"] * 0.2 + 
        df["制作分"] * 0.15 + 
        df["行业匹配"] * 0.25 + 
        df["节奏分"] * 0.1
    ).round(2)
    df = df.sort_values(by="综合评分", ascending=False).reset_index(drop=True)

    # 主界面标签页
    tab1, tab2, tab3 = st.tabs(["📋 视频列表", "🧐 单片深度评价", "📊 横向对比"])

    with tab1:
        st.subheader("全维度评价列表")
        st.dataframe(
            df[["视频标题", "综合评分", "互动率 (%)", "行业匹配", "一句话理由", "关键元素", "链接"]],
            column_config={"综合评分": st.column_config.NumberColumn("综合评分", format="%.1f ⭐"), "链接": st.column_config.LinkColumn("观看链接")},
            use_container_width=True
        )

    with tab2:
        st.subheader("单个影片详细评估")
        selected_video_title = st.selectbox("选择要分析的视频", df["视频标题"].tolist())
        v_data = df[df["视频标题"] == selected_video_title].iloc[0]
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.image(f"https://img.youtube.com/vi/{v_data['链接'].split('=')[-1]}/mqdefault.jpg", use_column_width=True)
            st.markdown(f"#### [{v_data['视频标题']}]({v_data['链接']})")
            st.write(f"**频道**: {v_data['频道']}")
        
        with c2:
            st.write(f"**综合得分: {v_data['综合评分']}**")
            st.progress(v_data['创意分']/10, text=f"创意表现力: {v_data['创意分']}")
            st.progress(v_data['制作分']/10, text=f"制作水准: {v_data['制作分']}")
            st.progress(v_data['行业匹配']/10, text=f"行业匹配度: {v_data['行业匹配']}")
            st.progress(v_data['节奏分']/10, text=f"节奏控制: {v_data['节奏分']}")
            st.success(f"**推荐理由**: {v_data['一句话理由']}")
            st.write(f"**关键元素**: `{v_data['关键元素']}`")

    with tab3:
        st.subheader("多影片横向对比")
        compare_videos = st.multiselect("选择 2-3 个视频进行对比", df["视频标题"].tolist(), default=df["视频标题"].tolist()[:2] if len(df) >= 2 else df["视频标题"].tolist())
        
        if len(compare_videos) >= 2:
            compare_df = df[df["视频标题"].isin(compare_videos)].set_index("视频标题")
            comparison_metrics = ["综合评分", "互动率 (%)", "创意分", "制作分", "行业匹配", "节奏分", "一句话理由", "关键元素"]
            st.table(compare_df[comparison_metrics].T)
            st.bar_chart(compare_df[["创意分", "制作分", "行业匹配", "节奏分"]])
        else:
            st.info("请至少选择两个视频进行对比。")
else:
    st.info("请在左侧点击“开始筛选”以获取数据。")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tips for Ad-Pro**:\n互动率 > 5% 通常被视为优质短视频，具有较高的商业转化潜力。")
