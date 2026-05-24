# XMU 课程网待办爬取

自动从 XMU 课程网（lnt.xmu.edu.cn）爬取未完成待办，按课程分类、按截止时间排序。**重点标注超时未交任务**，方便期末找助教补交。

## 为什么做这个

手机上点进企业微信 → 工作台 → 课程网 → 逐个课程翻找，我觉得比较麻烦。电脑网页版课程页面也没有直观的筛选。期末可能有多门课的过期作业要找助教补交，需要一个自动化的总览。

## 功能

- 遍历本学期全部课程，API 直调获取所有活动及完成度
- 自动筛选未完成项目（completeness < 100%），忽略纯阅读材料
- 分**进行中**和**已超时**两大区，各自按课程分组、按截止时间排序
- 超时分级着色：今天/1天 → 黄，2-7天 → 红，7天+ → 紫
- 生成 HTML 报告（`output/todos.html`）+ JSON 数据（`output/todos.json`）
- 有 24h 内截止的待办 → 桌面 `todos.lnk` 自动切换为警示图标
- 支持 Windows 定时任务，每小时后台自动运行

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 保存账号（仅首次）
python main.py --save-cred

# 3. 运行（自动登录，无需验证码）
python main.py --run

# 4. （可选）每小时自动运行
.\schedule.ps1
```

## 输出预览

HTML 报告在 `output/todos.html`，包含：

```
待办事项 — 2026-05-24
共 4 门课程，16 项待办

── 进行中 ──
  微积分I-2
    05-25 第十一周作业    0%

  概率统计(A)
    05-26 第六章作业      0%
    06-05 第八章作业      0%

── 已超时 ──
  概率统计(A)
    05-17 第一次作业      0%  超时6天
    05-22 第五章作业      0%  超时1天

  算法设计与分析
    03-24 动态规划线上课   0%  超时60天
    04-07 3月AC上传        0%  超时46天
```

## 文件结构

```
xmu-todo-scraper/
├── main.py              入口
├── config.yaml           配置文件
├── schedule.ps1          注册 Windows 定时任务
├── unschedule.ps1        删除定时任务
├── scraper/
│   ├── auth.py           登录 / XMU CAS 认证
│   ├── api.py            课程 & 活动 & 完成度 API
│   ├── models.py         数据模型
│   ├── formatter.py      HTML / JSON / 控制台输出
│   └── notifier.py       桌面快捷方式图标管理
├── data/                 凭据 & 图标（gitignore）
└── output/               生成的报告（gitignore）
```

## 技术栈

Python 3.11 + Playwright (Chromium) + PyYAML + Rich
