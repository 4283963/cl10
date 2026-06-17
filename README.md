# 地下管网巡检系统 - 安全路线规划平台

## 📋 项目概述

为市政环卫部门开发的地下管网智能巡检系统，核心功能是根据各管网节点的硫化氢（H₂S）和甲烷（CH₄）浓度数据，为巡检工人规划一条毒气浓度最低的安全巡检路线。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (React)                         │
│            · 管网拓扑图可视化 (SVG)                          │
│            · 安全路线高亮 (粗红线)                            │
│            · 节点气体浓度显示与交互                           │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / JSON
┌──────────────────────▼──────────────────────────────────────┐
│                     后端 (Flask + Python)                    │
│  · 接收巡检机器人上报的气体浓度数据 API                        │
│  · 数据存储 (MySQL)                                          │
│  · Dijkstra 安全路线规划算法                                  │
│  · 节点状态评估 (安全/预警/超标)                               │
└──────────────────────┬──────────────────────────────────────┘
                       │ SQLAlchemy
┌──────────────────────▼──────────────────────────────────────┐
│                   MySQL 数据库                               │
│  · pipe_nodes (管网节点表)                                   │
│  · pipe_connections (管网连接表)                              │
│  · gas_readings (气体浓度读数表)                              │
└─────────────────────────────────────────────────────────────┘
```

## 📁 项目目录结构

```
cl10/
├── backend/                    # 后端服务 (Flask + Python)
│   ├── app.py                  # Flask 主应用，含所有 API 路由
│   ├── config.py               # 配置文件（数据库连接、阈值等）
│   ├── models.py               # SQLAlchemy 数据库模型
│   ├── path_planner.py         # 路径规划算法 (Dijkstra)
│   ├── requirements.txt        # Python 依赖
│   ├── database/
│   │   └── init.sql            # MySQL 建表脚本
│   └── scripts/
│       └── robot_simulator.py  # 巡检机器人数据上报模拟器
│
└── frontend/                   # 前端应用 (React + Vite)
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx            # React 入口
        ├── App.jsx             # 主应用组件
        ├── components/
        │   └── TopologyCanvas.jsx  # 管网拓扑图 SVG 组件
        ├── services/
        │   └── api.js          # API 调用封装
        └── styles/
            └── global.css      # 全局样式
```

## 🚀 启动步骤

### 一、准备工作

1. **安装 MySQL 数据库**（确保服务已启动）

2. **创建数据库**（任选一种方式）：
   ```bash
   # 方式一：使用 SQL 脚本
   mysql -u root -p < backend/database/init.sql

   # 方式二：手动创建
   mysql -u root -p -e "CREATE DATABASE pipe_inspection CHARACTER SET utf8mb4;"
   ```
   > 如果你的 MySQL 用户名/密码不是 root/123456，请修改 `backend/config.py` 中的配置，或通过环境变量设置：
   ```bash
   export DB_USER=your_user
   export DB_PASSWORD=your_password
   ```

---

### 二、启动后端服务

```bash
cd backend

# 1. 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动后端 (端口 5000)
python app.py
```

首次启动时，程序会自动：
- 创建所有数据库表
- 插入示例管网数据（12个节点、16条连接）
- 插入初始气体浓度读数

后端健康检查：浏览器访问 http://localhost:5000/api/health

---

### 三、启动前端服务

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 启动前端开发服务器 (端口 3000)
npm run dev
```

浏览器访问：http://localhost:3000

---

### 四、（可选）启动巡检机器人模拟器

模拟器会定期向系统上报各节点的气体浓度数据，模拟真实的巡检机器人工作场景。

```bash
cd backend
source venv/bin/activate   # 确保已进入虚拟环境

# 单次上报
python scripts/robot_simulator.py once

# 持续上报（每15秒一次，推荐配合前端观察动态变化）
python scripts/robot_simulator.py continuous
```

## 🧪 功能验证

### 1. 查看管网拓扑图

打开前端页面后，默认显示：
- 蓝色方形带圆环 = 井口（出入口）
- 绿色圆形 = 安全节点
- 橙色圆形 = 预警节点（浓度≥阈值50%）
- 红色圆形（带光晕）= 超标节点（不可通行）

### 2. 计算安全巡检路线

1. 左侧面板选择起点（默认 WELL-A 井口）和终点（默认 WELL-B 井口）
2. 点击 **"🔍 计算安全巡检路线"** 按钮
3. 观察：
   - 拓扑图上出现 **粗红实线** 高亮的安全路径
   - 路径上的节点周围出现旋转的虚线圆环
   - 左侧显示路线分析报告（节点数、总距离、风险分、平均浓度）
   - 显示经过的每个节点详细信息

算法说明：
- 自动**跳过**所有超标节点（浓度超过阈值）
- 使用**加权 Dijkstra**：节点风险分（H₂S比值+CH₄比值）+ 距离权重
- 最终选择**综合风险最低**的路线

### 3. 查看节点详情

鼠标悬停到任意节点上，显示工具提示：
- 节点名称、ID、类型
- H₂S 浓度 (ppm) / 阈值 10 ppm
- CH₄ 浓度 (%LEL) / 阈值 1 %LEL
- 埋设深度

> 超标节点数值会显示为红色，预警节点为橙色

### 4. 测试超标节点避障

观察 J-05、J-07 节点（示例中标定为超标），计算路线时会自动绕开这些节点。

---

## 📡 API 接口列表

### 气体浓度数据上报（巡检机器人用）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/gas-readings` | 上报单条气体浓度数据 |
| POST | `/api/gas-readings/batch` | 批量上报多条数据 |
| GET | `/api/gas-readings/<node_id>` | 查询某节点历史读数 |
| GET | `/api/gas-readings/latest` | 获取所有节点最新读数 |

**POST /api/gas-readings 请求示例：**
```json
{
  "node_id": "J-01",
  "h2s_concentration": 3.25,
  "ch4_concentration": 0.185,
  "temperature": 22.5,
  "humidity": 68.0,
  "robot_id": "ROBOT-001",
  "recorded_at": "2026-06-17T08:30:00"
}
```

### 管网数据查询（前端用）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/nodes` | 获取所有节点（含状态） |
| GET | `/api/connections` | 获取所有管网连接 |
| GET | `/api/topology` | 同时获取节点+连接 |
| GET | `/api/thresholds` | 获取浓度阈值配置 |

### 路线规划

| 方法 | 路径 | 说明 |
|------|------|------|
| GET / POST | `/api/route` | 计算 A→B 安全路线 |

**GET /api/route?start_id=WELL-A&end_id=WELL-B 返回示例：**
```json
{
  "success": true,
  "path": ["WELL-A", "J-01", "J-02", "J-04", "J-06", "WELL-B"],
  "nodes": [...],
  "edges": [{ "from": "WELL-A", "to": "J-01" }, ...],
  "total_distance": 390.0,
  "total_risk_score": 2.456,
  "avg_h2s": 3.24,
  "avg_ch4": 0.245
}
```

---

## ⚙️ 配置说明

### 浓度阈值（可在 `backend/config.py` 修改）

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `H2S_THRESHOLD` | 10.0 | 硫化氢阈值（ppm），≥此值标记超标 |
| `CH4_THRESHOLD` | 1.0 | 甲烷阈值（%LEL），≥此值标记超标 |

### 数据库连接（环境变量优先）

```
DB_USER     默认 root
DB_PASSWORD 默认 123456
DB_HOST     默认 localhost
DB_PORT     默认 3306
DB_NAME     默认 pipe_inspection
```

---

## 🧠 算法核心说明

**文件位置：** [path_planner.py](backend/path_planner.py)

采用**改进的 Dijkstra 最短路径算法**，但"距离"不是物理长度，而是**综合风险值**：

```
节点风险分 = (H₂S浓度 / H₂S阈值) + (CH₄浓度 / CH₄阈值)

边权重 = 起点风险分 + 终点风险分 + (物理距离 / 1000)
```

算法约束：
- ❌ 若起点/终点本身超标 → 直接返回错误
- ❌ 遍历中跳过所有超标节点（视为不存在）
- ✅ 在所有可达路径中，选择**总风险值最小**的那条

---

## 🛠️ 技术栈

**后端：**
- Python 3.9+
- Flask 3.0（Web 框架）
- Flask-SQLAlchemy 3.x（ORM）
- PyMySQL（MySQL 驱动）
- heapq（Dijkstra 优先队列，Python 内置）

**前端：**
- React 18
- Vite 5（构建工具）
- SVG（拓扑图绘制，无第三方图库依赖）
- 原生 CSS（深色科技风 UI）

**数据库：**
- MySQL 5.7+ / 8.0

---

## 📌 注意事项

1. **生产环境部署**：请修改 `config.py` 中的 `SECRET_KEY`，并将 `debug=True` 关闭
2. **数据时效性**：算法自动使用每个节点**最近一次**的气体读数
3. **扩展性**：如需增加更多气体种类，在 `models.py` 和 `path_planner.py` 中添加字段和风险计算即可
4. **前端拓扑图**：支持鼠标拖拽平移 + 滚轮缩放
