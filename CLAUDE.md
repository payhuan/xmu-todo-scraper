# XMU TronClass 待办爬取工具

## 项目概述

每日自动爬取厦门大学 TronClass（畅课）LMS 平台的待办事项，按课程分类、按截止时间排序，输出 HTML + JSON 报告，并在有 24h 内截止的待办时将桌面快捷方式图标切换为警示图标。

## 技术栈

- Python 3.11, Playwright (Chromium), PyYAML, Rich

## 文件结构

```
xmu-todo-scraper/
├── main.py               CLI 入口
├── config.yaml           配置文件
├── requirements.txt      依赖
├── schedule.ps1          Windows 定时任务注册
├── unschedule.ps1        删除定时任务
├── scraper/
│   ├── auth.py           登录/凭证管理/session
│   ├── api.py            网络拦截 + 待办数据提取
│   ├── models.py         数据模型 (TodoItem, CourseTodos)
│   ├── formatter.py      HTML + JSON 输出
│   └── notifier.py       桌面快捷方式图标管理
├── data/
│   ├── auth_state.json   浏览器登录态（gitignore）
│   ├── credentials.json  账号密码 base64 存储（gitignore）
│   ├── normal.ico        正常图标
│   └── warning.ico       警示图标
└── output/
    ├── todos.html         待办报告
    └── todos.json         待办 JSON
```

## 关键实现

- **API 发现**: 不假设具体 API，用 Playwright 拦截首页所有 XHR，自动匹配含 todo_list/end_time/deadline 的响应
- **认证**: XMU CAS (ids.xmu.edu.cn)，Playwright 自动填表，base64 存凭据
- **Session 保持**: 每次成功爬取后刷新 storage_state，避免 cookie 过期
- **后台运行**: pythonw.exe + Windows 任务计划，不弹窗口

## 修改提醒

每次增减或修改功能后，务必更新 `使用说明.txt`，保持文档与代码同步。
