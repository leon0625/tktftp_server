# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Wails v2 桌面应用：TFTP client + server 二合一工具。Go 后端实现 TFTP 协议（基于 `github.com/pin/tftp/v3`），前端是 Vite 构建的纯 vanilla JS 单页（无框架），打包成单个桌面程序。无边框窗口（Frameless），自绘标题栏。

## 常用命令

所有 Go/Wails 命令需在 `wails_tftp/` 目录下执行：

```bash
# 开发运行（需要 WebKitGTK 4.1 系统依赖）
wails dev -tags webkit2_41

# 生产构建，产物在 build/bin/wails_tftp
wails build -tags webkit2_41

# Go 测试（当前仓库没有 *_test.go）
go test ./...

# 单独构建前端（产物在 frontend/dist，被 main.go 通过 go:embed 嵌入）
cd frontend && npm run build
```

### 使用工程内工具链（重要）

本机可能没有匹配的系统 Go/Wails，仓库根目录 `.tools/` 预置了完整工具链（`.tools/go/bin/go`、`.tools/bin/wails`、`.tools/gopath` 模块缓存），构建时必须用它：

```bash
PATH=/home/leon/code/github/tktftp_server/.tools/go/bin:/home/leon/code/github/tktftp_server/.tools/bin:$PATH \
GOPATH=/home/leon/code/github/tktftp_server/.tools/gopath \
GOTOOLCHAIN=local \
wails build -tags webkit2_41
```

### 端口 69 权限

TFTP server 监听 UDP 69（1024 以下端口），Linux 下需给二进制加 capability，否则启动失败：

```bash
sudo setcap cap_net_bind_service=+ep build/bin/wails_tftp
```

### 安装到系统

仓库根目录 `./ubuntu_install.sh` 将构建产物安装到 `/APP/wails_tftp/` 并注册桌面入口（复制 `wails_tftp.desktop` 到 `/usr/local/share/applications/`）。

## 架构

### 后端（`wails_tftp/app.go`，单文件约 870 行）

整个 Go 后端在一个 `App` 结构体 + 若干方法中，同时承担 server 和 client 两个角色：

- **TFTP Server**：`StartServer` 用 `tftp.NewServer(handleServerRead, handleServerWrite)` 创建，监听 `0.0.0.0:69`，根目录可随时切换（`StartServer` 内部先 `stopServer` 再重启）。写请求先写临时文件再 `os.Rename` 原子替换。
- **TFTP Client**：`StartClientTransfer` 校验入参后 `go runClientTransfer` 异步执行（get/put），配 `SetBlockSize(1468)`、`SetTimeout(1s)`、`SetRetries(5)`、`RequestTSize(true)`。
- **状态模型**：`transfers` map（服务端会话）+ 单个 `clientTransfer`（客户端会话），统一为 `TransferRecord`；`snapshot()` 加锁拷贝生成完整 `AppState`。
- **进度上报**：`progressReader`/`progressWriter` 包装 io 流，每个块更新后触发状态推送。
- **本机互传优化**：`isLocalTFTPHost` 检测客户端目标是否为本地 server（IP/主机名/回环解析 + 端口 69），若是则通过 `uploadSizes` map 预交换文件大小，让 put 时 server 端能显示总大小（pin/tftp 的 tsize 扩展在无 OACK 时不可靠）。
- **安全**：`safeJoin` 校验路径，防 `../` 目录穿越。
- **持久化**：根目录历史存 `~/.config/wails_tftp/history.json`（最多 20 条），客户端 Server IP 存 `settings.json`。

### 前后端通信（Wails 绑定）

- 前端通过 `frontend/wailsjs/go/main/App.js`（wails 自动生成的绑定）调用后端导出方法：`GetInitialState`、`StartServer`、`StopServer`、`StartClientTransfer`、`BrowseRoot`、`BrowseLocalFile`、`ChooseSaveFile`、`ClearCompleted`。
- 后端每次状态变化调用 `emitState()`，通过 `runtime.EventsEmit(ctx, "state", 完整AppState快照)` 全量推送；前端 `EventsOn('state', render)` 整体重渲染。错误经 `"app-error"` 事件到 toast。
- 前端 JS 侧只做展示逻辑（格式化、进度百分比、速度估算），不做状态持有；`state` 全局变量仅是最近一次快照的镜像。
- 注意：修改了 `app.go` 中导出方法签名后，`frontend/wailsjs/` 需要重新运行 `wails dev`/`wails build` 才会重新生成绑定；`frontend/src/main.js` 也要同步。

### 前端（`frontend/src/main.js` + `style.css`）

无框架纯 DOM：`app.innerHTML` 一次性渲染静态骨架（Server 面板 + Client 面板 + footer 统计 + 自绘标题栏），然后 `$()` 绑定事件、`render()` 用字符串模板重建表格行。改动 UI 时需同时留意 CSS（`style.css` 定义了全部主题样式）。

### 窗口配置（`wails_tftp/main.go`）

窗口 980×590、无边框、背景色 RGB(247,251,255)；资源经 `//go:embed all:frontend/dist` 嵌入。Linux 图标用 `appicon.png`。

## 详细文档

`wails_tftp/README.md` 记录了系统依赖安装（Ubuntu 24.04 的 WebKitGTK 4.1 等）、Wails CLI 安装方式等完整环境准备步骤，首次搭建环境时参考。
