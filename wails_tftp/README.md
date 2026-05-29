# Wails TFTP Tool

这是 TFTP 工具的 Wails 版本，后端使用 Go 实现 TFTP client/server，前端使用 Vite 构建静态页面，由 Wails 打包成单文件桌面程序。

## 技术栈

- 桌面框架：`github.com/wailsapp/wails/v2 v2.12.0`
- TFTP 协议库：`github.com/pin/tftp/v3 v3.1.0`
- 前端构建：`vite ^3.0.7`
- 运行时 WebView：Linux 下依赖 WebKitGTK

Go 间接依赖可以查看 `go.mod` 和 `go.sum`。前端依赖可以查看 `frontend/package.json` 和 `frontend/package-lock.json`。

## 系统依赖

Ubuntu 24.04 常见环境使用 WebKitGTK 4.1，推荐安装：

```bash
sudo apt update
sudo apt install -y build-essential pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev
```

还需要：

```bash
sudo apt install -y golang-go nodejs npm
```

如果系统仓库中的 Go 或 Node 版本太旧，可以自行安装新版。当前工程使用 `go 1.22.0`，Wails 构建需要可用的 Node/npm。

## 安装 Wails CLI

```bash
go install github.com/wailsapp/wails/v2/cmd/wails@v2.12.0
```

确认命令可用：

```bash
wails version
```

如果提示找不到 `wails`，把 Go bin 目录加入 `PATH`，例如：

```bash
export PATH="$HOME/go/bin:$PATH"
```

## 本地开发

进入 Wails 工程目录：

```bash
cd wails_tftp
```

安装前端依赖：

```bash
cd frontend
npm install
cd ..
```

启动开发模式：

```bash
wails dev -tags webkit2_41
```

说明：

- `-tags webkit2_41` 用于匹配 Ubuntu 24.04 上的 WebKitGTK 4.1。
- 如果你的系统安装的是 `libwebkit2gtk-4.0-dev`，可以尝试去掉 `-tags webkit2_41`。

## 本地编译打包

在 `wails_tftp` 目录下执行：

```bash
wails build -tags webkit2_41
```

生成的二进制文件在：

```bash
build/bin/wails_tftp
```

也可以先单独验证前端和 Go 后端：

```bash
cd frontend
npm run build
cd ..
go test ./...
```

## 使用工程内工具链构建

如果仓库根目录下已经准备了 `.tools` 目录，也可以使用本地工具链构建：

```bash
cd /home/leon/code/github/tktftp_server/wails_tftp
PATH=/home/leon/code/github/tktftp_server/.tools/go/bin:/home/leon/code/github/tktftp_server/.tools/bin:$PATH \
GOPATH=/home/leon/code/github/tktftp_server/.tools/gopath \
GOTOOLCHAIN=local \
wails build -tags webkit2_41
```

生成文件仍然是：

```bash
/home/leon/code/github/tktftp_server/wails_tftp/build/bin/wails_tftp
```

## UDP 69 端口权限

TFTP server 默认监听 UDP `69` 端口。Linux 下普通用户不能直接绑定 1024 以下端口，推荐给二进制加 capability：

```bash
sudo setcap cap_net_bind_service=+ep build/bin/wails_tftp
```

查看 capability：

```bash
getcap build/bin/wails_tftp
```

也可以用 `sudo` 启动，但不推荐长期这样使用桌面程序。

## 安装到系统

仓库根目录提供了 `ubuntu_install.sh`，用于把构建产物安装到 `/APP/wails_tftp`，并复制桌面入口：

```bash
cd /home/leon/code/github/tktftp_server
./ubuntu_install.sh
```

脚本会执行的关键动作：

- 复制 `wails_tftp/build/bin/wails_tftp` 到 `/APP/wails_tftp/`
- 给二进制设置 `cap_net_bind_service`
- 复制 `icon.png`
- 复制 `wails_tftp.desktop` 到 `/usr/local/share/applications/`

## 常用命令

```bash
# 开发运行
wails dev -tags webkit2_41

# 生产构建
wails build -tags webkit2_41

# Go 测试
go test ./...

# 前端构建
cd frontend && npm run build
```
