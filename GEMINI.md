# Project Overview: YouTube 视频评价系统 (Ad-Pro Edition)

这是一个专为广告从业者设计的 **YouTube 短视频快速评价工具**。旨在通过简单的关键词搜索，接入 YouTube API，快速筛选并评估视频的商业价值（互动率、适配度等）。

## 🛠️ 技术栈
*   **后端/UI**: Python + [Streamlit](https://streamlit.io/) (最直接的 Python UI 框架)
*   **API**: YouTube Data API v3
*   **核心逻辑**: 互动率计算 (Engagement Rate) = (点赞 + 评论) / 观看量

## 📂 目录结构
*   `app.py`: 主程序逻辑与 UI。
*   `requirements.txt`: 项目依赖。
*   `.env`: (需手动创建) 存放 YouTube API Key。

## 🚀 快速开始
1.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **配置 API**:
    在根目录创建 `.env` 文件，添加：`YOUTUBE_API_KEY=你的API密钥`
3.  **运行**:
    ```bash
    streamlit run app.py
    ```

## 📝 评价维度
1.  **互动效率**: 识别哪些视频虽然播放量不高但粉丝粘性极强。
2.  **内容适配**: 通过标签和描述关键词匹配广告需求。
