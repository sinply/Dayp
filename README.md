# Dayp - 每日使用报告

本地运行的电脑使用情况监控仪表盘，记录软件使用时长、AI 热点新闻、邮件摘要，并生成每周工作总结。

## 功能

- **软件使用监控**：每秒采样前台活动窗口，按进程汇总当日使用时长与占比
- **AI 热点新闻**：通过 Hacker News API 抓取热门 AI 相关新闻（每小时刷新）
- **邮件摘要**：通过 Outlook COM 自动化读取本地 Outlook 已同步邮件（近 7 天）
- **周报总结**：基于软件使用 + 邮件数据，按规则模板生成每周工作总结
- **仪表盘**：浏览器访问，环形图 + 堆叠柱状图可视化

## 环境要求

- Windows 10/11
- Python 3.12+（原生 Windows CPython，不支持 MSYS2/MinGW 版）
- Outlook 桌面客户端（已登录账号并同步过邮件）

## 安装

```powershell
cd D:\Exercise\AI\Dayp

# 创建虚拟环境
python -m venv .venv

# 激活并安装依赖
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> 如系统未安装原生 Python，从 https://www.python.org/downloads/ 下载安装，勾选 "Add to PATH"。

## 启动

需要开两个终端。

**终端 1 - 启动后台 agent**（采集数据）：

```powershell
cd D:\Exercise\AI\Dayp
.\.venv\Scripts\Activate.ps1
python -m agent.main
```

agent 会并行运行：
- 窗口采样器（每秒）
- 新闻采集器（每小时）
- 邮件采集器（每小时）
- 每日聚合器（凌晨 0 点汇总前一天数据）

按 `Ctrl+C` 停止。

**终端 2 - 启动 Web 服务**：

```powershell
cd D:\Exercise\AI\Dayp
.\.venv\Scripts\Activate.ps1
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 http://127.0.0.1:8000

## 目录结构

```
Dayp/
├── agent/
│   ├── main.py              # agent 入口，调度三个采集器
│   ├── window_tracker.py    # 前台窗口采样（pywin32 + psutil）
│   ├── news_fetcher.py      # Hacker News API + AI 关键词过滤
│   └── mail_fetcher.py      # Outlook COM 读取邮件
├── api/
│   ├── main.py              # FastAPI 应用
│   ├── db.py                # SQLite 连接与建表
│   └── routes/
│       ├── usage.py         # /api/usage/today, /api/usage/week
│       ├── emails.py        # /api/emails
│       ├── news.py          # /api/news
│       └── summary.py       # /api/summary/week
├── web/
│   ├── index.html           # 仪表盘页面
│   ├── style.css            # 暗色主题样式
│   └── app.js               # 数据加载与 Chart.js 渲染
├── data/
│   └── dayp.db              # SQLite 数据库（运行时生成）
├── requirements.txt
└── README.md
```

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/usage/today` | 今日各软件使用时长与占比 |
| GET | `/api/usage/week` | 近 7 日每日堆叠图数据 |
| GET | `/api/usage/date/{YYYY-MM-DD}` | 指定日期的使用情况 |
| GET | `/api/emails?days=7` | 近 N 天邮件列表 |
| GET | `/api/news?limit=30` | 最新 AI 新闻 |
| GET | `/api/summary/week` | 周报总结文本 |
| GET | `/api/health` | 健康检查 |

## 数据存储

所有数据存于 `data/dayp.db`（SQLite），包含 4 张表：
- `app_usage` - 软件使用明细（每秒采样）
- `daily_summary` - 每日按进程聚合
- `emails` - 邮件记录（EntryID 去重）
- `news` - AI 新闻（HN ID 去重）

## 隐私

- 所有数据仅存于本地，不上传任何服务器
- 邮件通过本地 Outlook COM 读取，不经过网络
- 唯一的外部网络请求是 Hacker News API（公开数据）

## 故障排查

**Q: 启动 agent 报 `No module named 'win32gui'`**
A: 确认使用的是原生 Windows Python，不是 MSYS2。运行 `python -c "import sys; print(sys.platform)"` 应输出 `win32`，且 `sys.executable` 不在 `C:\msys64` 下。

**Q: 邮件列表为空**
A: 确保 Outlook 桌面客户端已安装、账号已登录、收件箱有邮件。agent 运行时 Outlook 无需打开，但账号必须已配置。

**Q: 新闻列表为空**
A: 检查网络能否访问 `https://hacker-news.firebaseio.com`。首次启动需等待约 10-30 秒采集。

## 停止服务

- agent：在终端 1 按 `Ctrl+C`
- Web：在终端 2 按 `Ctrl+C`
