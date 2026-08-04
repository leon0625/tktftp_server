package main

import (
	"bytes"
	"io"
	"net"
	"os"
	"path/filepath"
	"testing"
)

// fakeWriterTo 模拟 pin/tftp 服务端接收上传（WRQ）时传入的 receiver：
// WriteTo 由库在收完数据后调用。size/ok 模拟 WRQ 中是否带 tsize 选项。
type fakeWriterTo struct {
	data []byte
	size int64
	ok   bool
}

func (w *fakeWriterTo) WriteTo(dst io.Writer) (int64, error) {
	n, err := dst.Write(w.data)
	return int64(n), err
}

func (w *fakeWriterTo) Size() (int64, bool) { return w.size, w.ok }

func (w *fakeWriterTo) RemoteAddr() net.UDPAddr {
	return net.UDPAddr{IP: net.IPv4(192, 168, 1, 10), Port: 45678}
}

// fakeReaderFrom 模拟 pin/tftp 服务端发送文件（RRQ）时传入的 sender：
// ReadFrom 由库在发完所有数据后调用，数据全部读取并丢弃。
type fakeReaderFrom struct {
	received bytes.Buffer
}

func (r *fakeReaderFrom) ReadFrom(src io.Reader) (int64, error) {
	return io.Copy(&r.received, src)
}

func (r *fakeReaderFrom) RemoteAddr() net.UDPAddr {
	return net.UDPAddr{IP: net.IPv4(192, 168, 1, 10), Port: 45678}
}

func (r *fakeReaderFrom) SetSize(int64) {}

func newTestApp(t *testing.T) *App {
	t.Helper()
	app := NewApp()
	app.ctx = nil // emitState/notifyState 在 ctx 为 nil 时直接跳过
	app.rootDir = t.TempDir()
	return app
}

// 服务器接收上传且客户端未带 tsize（WRQ 无 tsize 选项）：
// 完成后记录必须是 Completed 且 BytesDone == BytesTotal，前端才会显示 100%。
func TestServerWriteProgressWithoutTsize(t *testing.T) {
	app := newTestApp(t)
	data := []byte("hello tftp server")
	if err := app.handleServerWrite("put.bin", &fakeWriterTo{data: data}); err != nil {
		t.Fatalf("handleServerWrite: %v", err)
	}
	app.mu.Lock()
	defer app.mu.Unlock()
	if len(app.transfers) != 1 {
		t.Fatalf("want 1 transfer record, got %d", len(app.transfers))
	}
	var rec *TransferRecord
	for _, r := range app.transfers {
		rec = r
	}
	if rec.Status != "Completed" {
		t.Fatalf("status = %s, want Completed", rec.Status)
	}
	if rec.BytesDone != int64(len(data)) {
		t.Errorf("BytesDone = %d, want %d", rec.BytesDone, len(data))
	}
	if rec.BytesTotal != int64(len(data)) {
		t.Errorf("BytesTotal = %d, want %d (corrected to done when unknown)", rec.BytesTotal, len(data))
	}
	if got, err := os.ReadFile(filepath.Join(app.rootDir, "put.bin")); err != nil || !bytes.Equal(got, data) {
		t.Errorf("file content mismatch: err=%v got=%q", err, got)
	}
}

// 服务器接收上传且客户端带 tsize：BytesTotal 应为协商值，完成后 100%。
func TestServerWriteProgressWithTsize(t *testing.T) {
	app := newTestApp(t)
	data := []byte("hello tftp server with tsize")
	if err := app.handleServerWrite("put2.bin", &fakeWriterTo{data: data, size: int64(len(data)), ok: true}); err != nil {
		t.Fatalf("handleServerWrite: %v", err)
	}
	app.mu.Lock()
	defer app.mu.Unlock()
	for _, rec := range app.transfers {
		if rec.Status != "Completed" {
			t.Fatalf("status = %s, want Completed", rec.Status)
		}
		if rec.BytesTotal != int64(len(data)) {
			t.Errorf("BytesTotal = %d, want %d", rec.BytesTotal, len(data))
		}
	}
}

// 服务器发送文件：进度最终到达 100%（BytesDone == BytesTotal == 文件大小）。
func TestServerReadProgress(t *testing.T) {
	app := newTestApp(t)
	payload := make([]byte, 3000) // 跨多个 512/1468 字节块
	for i := range payload {
		payload[i] = byte(i)
	}
	if err := os.WriteFile(filepath.Join(app.rootDir, "get.bin"), payload, 0644); err != nil {
		t.Fatal(err)
	}
	rf := &fakeReaderFrom{}
	if err := app.handleServerRead("get.bin", rf); err != nil {
		t.Fatalf("handleServerRead: %v", err)
	}
	if rf.received.Len() != len(payload) {
		t.Fatalf("received %d bytes, want %d", rf.received.Len(), len(payload))
	}
	app.mu.Lock()
	defer app.mu.Unlock()
	for _, rec := range app.transfers {
		if rec.Status != "Completed" {
			t.Fatalf("status = %s, want Completed", rec.Status)
		}
		if rec.BytesTotal != int64(len(payload)) || rec.BytesDone != int64(len(payload)) {
			t.Errorf("progress = %d/%d, want %d/%d", rec.BytesDone, rec.BytesTotal, len(payload), len(payload))
		}
	}
}
