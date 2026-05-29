package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/pin/tftp/v3"
	"github.com/wailsapp/wails/v2/pkg/runtime"
)

const listenPort = 69
const maxRootHistory = 20
const defaultClientServerIP = "192.168.1.10"

type TransferRecord struct {
	ID         string `json:"id"`
	FileName   string `json:"fileName"`
	Direction  string `json:"direction"`
	Status     string `json:"status"`
	Peer       string `json:"peer"`
	BytesDone  int64  `json:"bytesDone"`
	BytesTotal int64  `json:"bytesTotal"`
	StartedAt  int64  `json:"startedAt"`
	EndedAt    int64  `json:"endedAt"`
	Error      string `json:"error"`
}

type Counts struct {
	Total      int `json:"total"`
	Completed  int `json:"completed"`
	InProgress int `json:"inProgress"`
	Failed     int `json:"failed"`
}

type AppState struct {
	RootDirectory  string           `json:"rootDirectory"`
	RootHistory    []string         `json:"rootHistory"`
	ListenIP       string           `json:"listenIP"`
	ServerIP       string           `json:"serverIP"`
	Port           int              `json:"port"`
	ServerStatus   string           `json:"serverStatus"`
	Transfers      []TransferRecord `json:"transfers"`
	ClientTransfer *TransferRecord  `json:"clientTransfer"`
	Counts         Counts           `json:"counts"`
}

type ClientTransferRequest struct {
	Action     string `json:"action"`
	Host       string `json:"host"`
	Port       int    `json:"port"`
	LocalFile  string `json:"localFile"`
	RemoteFile string `json:"remoteFile"`
}

type App struct {
	ctx            context.Context
	mu             sync.Mutex
	rootDir        string
	rootHistory    []string
	clientServerIP string
	server         *tftp.Server
	serverStatus   string
	transfers      map[string]*TransferRecord
	clientTransfer *TransferRecord
	uploadSizes    map[string]int64
	nextID         int64
}

func NewApp() *App {
	cwd, err := os.Getwd()
	if err != nil {
		cwd = "."
	}
	history := loadRootHistory()
	if len(history) > 0 {
		cwd = history[0]
	}
	return &App{
		rootDir:        cwd,
		rootHistory:    ensureHistoryPath(history, cwd),
		clientServerIP: loadClientServerIP(),
		serverStatus:   "Stopped",
		transfers:      map[string]*TransferRecord{},
		uploadSizes:    map[string]int64{},
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	go func() {
		time.Sleep(200 * time.Millisecond)
		_ = a.StartServer(a.rootDir)
	}()
}

func (a *App) shutdown(_ context.Context) {
	a.stopServer()
}

func (a *App) GetInitialState() AppState {
	return a.snapshot()
}

func (a *App) BrowseRoot() (string, error) {
	dir, err := runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{
		Title:            "Select TFTP Root Directory",
		DefaultDirectory: a.rootDir,
	})
	if err != nil || dir == "" {
		return "", err
	}
	return dir, nil
}

func (a *App) BrowseLocalFile() (string, error) {
	return runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "Select Local File",
	})
}

func (a *App) ChooseSaveFile(defaultName string) (string, error) {
	return runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{
		Title:           "Save Downloaded File",
		DefaultFilename: defaultName,
	})
}

func (a *App) StartServer(rootDir string) error {
	rootDir = strings.TrimSpace(rootDir)
	if rootDir == "" {
		return fmt.Errorf("root directory is required")
	}
	info, err := os.Stat(rootDir)
	if err != nil {
		a.setServerStatus("Failed")
		return err
	}
	if !info.IsDir() {
		a.setServerStatus("Failed")
		return fmt.Errorf("%s is not a directory", rootDir)
	}

	a.stopServer()
	a.mu.Lock()
	a.rootDir = rootDir
	a.rootHistory = ensureHistoryPath(a.rootHistory, rootDir)
	a.serverStatus = "Starting"
	history := append([]string(nil), a.rootHistory...)
	a.mu.Unlock()
	saveRootHistory(history)
	a.emitState()

	server := tftp.NewServer(a.handleServerRead, a.handleServerWrite)
	server.SetRetries(5)
	server.SetTimeout(5 * time.Second)

	a.mu.Lock()
	a.server = server
	a.mu.Unlock()

	go func() {
		a.setServerStatus("Running")
		if err := server.ListenAndServe(fmt.Sprintf("0.0.0.0:%d", listenPort)); err != nil {
			a.mu.Lock()
			current := a.server == server
			a.mu.Unlock()
			if current {
				a.setServerStatus("Failed")
				a.emitError(err.Error())
			}
		}
	}()
	return nil
}

func (a *App) stopServer() {
	a.mu.Lock()
	server := a.server
	a.server = nil
	a.serverStatus = "Stopped"
	a.mu.Unlock()
	if server != nil {
		server.Shutdown()
	}
	a.emitState()
}

func (a *App) StopServer() {
	a.stopServer()
}

func (a *App) ClearCompleted() {
	a.mu.Lock()
	for id, record := range a.transfers {
		if record.Status == "Completed" || record.Status == "Failed" {
			delete(a.transfers, id)
		}
	}
	a.mu.Unlock()
	a.emitState()
}

func (a *App) StartClientTransfer(req ClientTransferRequest) error {
	req.Action = strings.ToLower(strings.TrimSpace(req.Action))
	req.Host = strings.TrimSpace(req.Host)
	req.LocalFile = strings.TrimSpace(req.LocalFile)
	req.RemoteFile = strings.TrimSpace(req.RemoteFile)
	if req.Port == 0 {
		req.Port = listenPort
	}
	if req.Host == "" || req.LocalFile == "" {
		return fmt.Errorf("server IP and local file are required")
	}
	if req.Action != "get" && req.Action != "put" {
		return fmt.Errorf("unknown transfer action: %s", req.Action)
	}
	if req.Action == "get" && req.RemoteFile == "" {
		return fmt.Errorf("remote file is required for get")
	}
	if req.Action == "put" && req.RemoteFile == "" {
		req.RemoteFile = filepath.Base(req.LocalFile)
	}
	a.setClientServerIP(req.Host)
	go a.runClientTransfer(req)
	return nil
}

func (a *App) handleServerRead(filename string, rf io.ReaderFrom) error {
	peer := transferPeer(rf)
	id := a.addTransfer(filename, "Sending", "Sending", peer, 0)

	path, err := safeJoin(a.rootDir, filename)
	if err != nil {
		a.finishTransfer(id, "Failed", err)
		return err
	}
	file, err := os.Open(path)
	if err != nil {
		a.finishTransfer(id, "Failed", err)
		return err
	}
	defer file.Close()

	var total int64
	if info, err := file.Stat(); err == nil {
		total = info.Size()
	}
	if outgoing, ok := rf.(tftp.OutgoingTransfer); ok && total > 0 {
		outgoing.SetSize(total)
	}
	a.updateTransferProgress(id, 0, total)
	reader := &progressReader{
		reader: file,
		onProgress: func(done int64) {
			a.updateTransferProgress(id, done, total)
		},
	}
	_, err = rf.ReadFrom(reader)
	if err != nil {
		a.finishTransfer(id, "Failed", err)
		return err
	}
	a.finishTransfer(id, "Completed", nil)
	return nil
}

func (a *App) handleServerWrite(filename string, wt io.WriterTo) error {
	path, err := safeJoin(a.rootDir, filename)
	if err != nil {
		return err
	}
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	file, err := os.CreateTemp(dir, "."+filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	tempPath := file.Name()
	defer file.Close()
	defer os.Remove(tempPath)

	var total int64
	if incoming, ok := wt.(tftp.IncomingTransfer); ok {
		if size, hasSize := incoming.Size(); hasSize {
			total = size
		}
	}
	if total == 0 {
		total = a.takeUploadSize(filename)
	}
	peer := transferPeer(wt)
	id := a.addTransfer(filename, "Receiving", "Receiving", peer, total)
	writer := &progressWriter{
		writer: file,
		onProgress: func(done int64) {
			a.updateTransferProgress(id, done, total)
		},
	}
	written, err := wt.WriteTo(writer)
	if err != nil {
		a.finishTransfer(id, "Failed", err)
		return err
	}
	if written > 0 && total == 0 {
		total = written
	}
	a.updateTransferProgress(id, written, total)
	if err := file.Close(); err != nil {
		a.finishTransfer(id, "Failed", err)
		return err
	}
	if err := os.Rename(tempPath, path); err != nil {
		a.finishTransfer(id, "Failed", err)
		return err
	}
	a.finishTransfer(id, "Completed", nil)
	return nil
}

func (a *App) runClientTransfer(req ClientTransferRequest) {
	peer := net.JoinHostPort(req.Host, strconv.Itoa(req.Port))
	status := "Receiving"
	direction := "Get"
	total := int64(0)
	name := req.RemoteFile
	if req.Action == "put" {
		status = "Sending"
		direction = "Put"
		name = req.RemoteFile
		if info, err := os.Stat(req.LocalFile); err == nil {
			total = info.Size()
		}
		if total > 0 && isLocalTFTPHost(req.Host, req.Port) {
			a.setUploadSize(req.RemoteFile, total)
			defer a.clearUploadSize(req.RemoteFile)
		}
	} else if isLocalTFTPHost(req.Host, req.Port) {
		total = a.localRootFileSize(req.RemoteFile)
	}
	id := a.setClientTransfer(name, direction, status, peer, total)

	client, err := tftp.NewClient(peer)
	if err != nil {
		a.finishClientTransfer(id, "Failed", err)
		return
	}
	client.SetTimeout(1 * time.Second)
	client.SetRetries(5)
	client.SetBlockSize(1468)
	client.RequestTSize(true)

	if req.Action == "get" {
		a.runClientGet(id, client, req, total)
		return
	}
	a.runClientPut(id, client, req, total)
}

func (a *App) runClientGet(id string, client *tftp.Client, req ClientTransferRequest, total int64) {
	transfer, err := client.Receive(req.RemoteFile, "octet")
	if err != nil {
		a.finishClientTransfer(id, "Failed", err)
		return
	}
	if incoming, ok := transfer.(tftp.IncomingTransfer); ok {
		if size, hasSize := incoming.Size(); hasSize {
			total = size
			a.updateClientProgress(id, 0, total)
		}
	}
	file, err := os.Create(req.LocalFile)
	if err != nil {
		a.finishClientTransfer(id, "Failed", err)
		return
	}
	defer file.Close()

	writer := &progressWriter{
		writer: file,
		onProgress: func(done int64) {
			a.updateClientProgress(id, done, total)
		},
	}
	written, err := transfer.WriteTo(writer)
	if err != nil {
		a.finishClientTransfer(id, "Failed", err)
		return
	}
	if written > 0 && total == 0 {
		total = written
	}
	a.updateClientProgress(id, written, total)
	a.finishClientTransfer(id, "Completed", nil)
}

func (a *App) runClientPut(id string, client *tftp.Client, req ClientTransferRequest, total int64) {
	file, err := os.Open(req.LocalFile)
	if err != nil {
		a.finishClientTransfer(id, "Failed", err)
		return
	}
	defer file.Close()

	transfer, err := client.Send(req.RemoteFile, "octet")
	if err != nil {
		a.finishClientTransfer(id, "Failed", err)
		return
	}
	if outgoing, ok := transfer.(tftp.OutgoingTransfer); ok && total > 0 {
		outgoing.SetSize(total)
	}
	reader := &progressReader{
		reader: file,
		onProgress: func(done int64) {
			a.updateClientProgress(id, done, total)
		},
	}
	written, err := transfer.ReadFrom(reader)
	if err != nil {
		a.finishClientTransfer(id, "Failed", err)
		return
	}
	if written > 0 && total == 0 {
		total = written
	}
	a.updateClientProgress(id, written, total)
	a.finishClientTransfer(id, "Completed", nil)
}

func (a *App) setClientTransfer(fileName, direction, status, peer string, total int64) string {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.nextID++
	id := fmt.Sprintf("client-%d-%d", time.Now().UnixNano(), a.nextID)
	a.clientTransfer = &TransferRecord{
		ID:         id,
		FileName:   fileName,
		Direction:  direction,
		Status:     status,
		Peer:       peer,
		BytesTotal: total,
		StartedAt:  time.Now().UnixMilli(),
	}
	go a.emitState()
	return id
}

func (a *App) updateClientProgress(id string, done int64, total int64) {
	a.mu.Lock()
	record := a.clientTransfer
	if record != nil && record.ID == id {
		record.BytesDone = done
		if total > 0 {
			record.BytesTotal = total
		}
	}
	a.mu.Unlock()
	a.emitState()
}

func (a *App) finishClientTransfer(id, status string, err error) {
	a.mu.Lock()
	record := a.clientTransfer
	if record != nil && record.ID == id {
		record.Status = status
		record.EndedAt = time.Now().UnixMilli()
		if record.BytesTotal == 0 && record.BytesDone > 0 {
			record.BytesTotal = record.BytesDone
		}
		if record.BytesTotal > 0 && status == "Completed" {
			record.BytesDone = record.BytesTotal
		}
		if err != nil {
			record.Error = err.Error()
		}
	}
	a.mu.Unlock()
	a.emitState()
}

func (a *App) addTransfer(fileName, direction, status, peer string, total int64) string {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.nextID++
	id := fmt.Sprintf("%d-%d", time.Now().UnixNano(), a.nextID)
	a.transfers[id] = &TransferRecord{
		ID:         id,
		FileName:   fileName,
		Direction:  direction,
		Status:     status,
		Peer:       peer,
		BytesTotal: total,
		StartedAt:  time.Now().UnixMilli(),
	}
	go a.emitState()
	return id
}

func (a *App) updateTransferProgress(id string, done int64, total int64) {
	a.mu.Lock()
	record := a.transfers[id]
	if record != nil {
		record.BytesDone = done
		if total > 0 {
			record.BytesTotal = total
		}
	}
	a.mu.Unlock()
	a.emitState()
}

func (a *App) finishTransfer(id, status string, err error) {
	a.mu.Lock()
	record := a.transfers[id]
	if record != nil {
		record.Status = status
		record.EndedAt = time.Now().UnixMilli()
		if record.BytesTotal == 0 && record.BytesDone > 0 {
			record.BytesTotal = record.BytesDone
		}
		if record.BytesTotal > 0 && status == "Completed" {
			record.BytesDone = record.BytesTotal
		}
		if err != nil {
			record.Error = err.Error()
		}
	}
	a.mu.Unlock()
	a.emitState()
}

func (a *App) setServerStatus(status string) {
	a.mu.Lock()
	a.serverStatus = status
	a.mu.Unlock()
	a.emitState()
}

func (a *App) snapshot() AppState {
	a.mu.Lock()
	defer a.mu.Unlock()

	transfers := make([]TransferRecord, 0, len(a.transfers))
	for _, record := range a.transfers {
		transfers = append(transfers, *record)
	}
	sort.Slice(transfers, func(i, j int) bool {
		return transfers[i].StartedAt > transfers[j].StartedAt
	})

	counts := Counts{Total: len(transfers)}
	for _, record := range transfers {
		switch record.Status {
		case "Completed":
			counts.Completed++
		case "Failed":
			counts.Failed++
		case "Sending", "Receiving", "Transferring":
			counts.InProgress++
		}
	}

	rootHistory := append([]string(nil), a.rootHistory...)
	var clientTransfer *TransferRecord
	if a.clientTransfer != nil {
		copy := *a.clientTransfer
		clientTransfer = &copy
	}

	return AppState{
		RootDirectory:  a.rootDir,
		RootHistory:    rootHistory,
		ListenIP:       "0.0.0.0",
		ServerIP:       a.clientServerIP,
		Port:           listenPort,
		ServerStatus:   a.serverStatus,
		Transfers:      transfers,
		ClientTransfer: clientTransfer,
		Counts:         counts,
	}
}

func (a *App) emitState() {
	if a.ctx == nil {
		return
	}
	runtime.EventsEmit(a.ctx, "state", a.snapshot())
}

func (a *App) emitError(message string) {
	if a.ctx == nil {
		return
	}
	runtime.EventsEmit(a.ctx, "app-error", message)
}

func (a *App) setClientServerIP(serverIP string) {
	serverIP = strings.TrimSpace(serverIP)
	if serverIP == "" {
		return
	}
	a.mu.Lock()
	a.clientServerIP = serverIP
	a.mu.Unlock()
	saveClientServerIP(serverIP)
	a.emitState()
}

func (a *App) setUploadSize(name string, size int64) {
	if size <= 0 {
		return
	}
	a.mu.Lock()
	a.uploadSizes[transferSizeKey(name)] = size
	a.mu.Unlock()
}

func (a *App) takeUploadSize(name string) int64 {
	a.mu.Lock()
	defer a.mu.Unlock()
	key := transferSizeKey(name)
	size := a.uploadSizes[key]
	delete(a.uploadSizes, key)
	return size
}

func (a *App) clearUploadSize(name string) {
	a.mu.Lock()
	delete(a.uploadSizes, transferSizeKey(name))
	a.mu.Unlock()
}

func (a *App) localRootFileSize(name string) int64 {
	a.mu.Lock()
	rootDir := a.rootDir
	a.mu.Unlock()
	path, err := safeJoin(rootDir, name)
	if err != nil {
		return 0
	}
	info, err := os.Stat(path)
	if err != nil || info.IsDir() {
		return 0
	}
	return info.Size()
}

type progressReader struct {
	reader     io.Reader
	done       int64
	onProgress func(done int64)
}

func (r *progressReader) Read(p []byte) (int, error) {
	n, err := r.reader.Read(p)
	if n > 0 {
		r.done += int64(n)
		r.onProgress(r.done)
	}
	return n, err
}

type progressWriter struct {
	writer     io.Writer
	done       int64
	onProgress func(done int64)
}

func (w *progressWriter) Write(p []byte) (int, error) {
	n, err := w.writer.Write(p)
	if n > 0 {
		w.done += int64(n)
		w.onProgress(w.done)
	}
	return n, err
}

type remoteAddrProvider interface {
	RemoteAddr() net.UDPAddr
}

func transferPeer(value interface{}) string {
	if peer, ok := value.(remoteAddrProvider); ok {
		addr := peer.RemoteAddr()
		return addr.String()
	}
	return ""
}

func safeJoin(root, name string) (string, error) {
	name = strings.TrimLeft(filepath.Clean(name), string(filepath.Separator))
	path := filepath.Join(root, name)
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return "", err
	}
	if rel == "." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || rel == ".." {
		return "", fmt.Errorf("invalid file path: %s", name)
	}
	return path, nil
}

func transferSizeKey(name string) string {
	return filepath.ToSlash(filepath.Clean(strings.TrimSpace(name)))
}

func isLocalTFTPHost(host string, port int) bool {
	if port != listenPort {
		return false
	}
	host = strings.Trim(strings.TrimSpace(host), "[]")
	if host == "" {
		return false
	}
	if strings.EqualFold(host, "localhost") {
		return true
	}
	ip := net.ParseIP(host)
	if ip == nil {
		ips, err := net.LookupIP(host)
		if err != nil {
			return false
		}
		for _, candidate := range ips {
			if isLocalIP(candidate) {
				return true
			}
		}
		return false
	}
	return isLocalIP(ip)
}

func isLocalIP(ip net.IP) bool {
	if ip == nil {
		return false
	}
	if ip.IsLoopback() || ip.IsUnspecified() {
		return true
	}
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return false
	}
	for _, addr := range addrs {
		var local net.IP
		switch value := addr.(type) {
		case *net.IPNet:
			local = value.IP
		case *net.IPAddr:
			local = value.IP
		}
		if local != nil && local.Equal(ip) {
			return true
		}
	}
	return false
}

func historyFilePath() string {
	configDir, err := os.UserConfigDir()
	if err != nil {
		return "wails_tftp_history.json"
	}
	dir := filepath.Join(configDir, "wails_tftp")
	_ = os.MkdirAll(dir, 0755)
	return filepath.Join(dir, "history.json")
}

func settingsFilePath() string {
	configDir, err := os.UserConfigDir()
	if err != nil {
		return "wails_tftp_settings.json"
	}
	dir := filepath.Join(configDir, "wails_tftp")
	_ = os.MkdirAll(dir, 0755)
	return filepath.Join(dir, "settings.json")
}

type appSettings struct {
	ClientServerIP string `json:"clientServerIP"`
}

func loadClientServerIP() string {
	data, err := os.ReadFile(settingsFilePath())
	if err != nil {
		return defaultClientServerIP
	}
	var settings appSettings
	if err := json.Unmarshal(data, &settings); err != nil {
		return defaultClientServerIP
	}
	serverIP := strings.TrimSpace(settings.ClientServerIP)
	if serverIP == "" {
		return defaultClientServerIP
	}
	return serverIP
}

func saveClientServerIP(serverIP string) {
	serverIP = strings.TrimSpace(serverIP)
	if serverIP == "" {
		return
	}
	data, err := json.MarshalIndent(appSettings{ClientServerIP: serverIP}, "", "  ")
	if err != nil {
		return
	}
	_ = os.WriteFile(settingsFilePath(), data, 0644)
}

func loadRootHistory() []string {
	data, err := os.ReadFile(historyFilePath())
	if err != nil {
		return nil
	}
	var history []string
	if err := json.Unmarshal(data, &history); err != nil {
		return nil
	}
	return normalizeHistory(history)
}

func saveRootHistory(history []string) {
	data, err := json.MarshalIndent(normalizeHistory(history), "", "  ")
	if err != nil {
		return
	}
	_ = os.WriteFile(historyFilePath(), data, 0644)
}

func ensureHistoryPath(history []string, path string) []string {
	path = strings.TrimSpace(path)
	if path == "" {
		return normalizeHistory(history)
	}
	next := []string{path}
	for _, item := range history {
		if item != path {
			next = append(next, item)
		}
	}
	return normalizeHistory(next)
}

func normalizeHistory(history []string) []string {
	seen := map[string]bool{}
	next := make([]string, 0, len(history))
	for _, item := range history {
		item = strings.TrimSpace(item)
		if item == "" || seen[item] {
			continue
		}
		seen[item] = true
		next = append(next, item)
		if len(next) >= maxRootHistory {
			break
		}
	}
	return next
}
