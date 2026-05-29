# Wails TFTP Tool

Modern Wails + Go implementation of the TFTP tool.

## Build

Ubuntu 24.04 commonly provides WebKitGTK 4.1, so build with:

```bash
wails build -tags webkit2_41
```

The binary is generated at:

```bash
build/bin/wails_tftp
```

## Notes

- The backend uses `github.com/pin/tftp/v3`.
- The server listens on UDP port `69`, so normal users may need elevated privileges or port-capability configuration.
