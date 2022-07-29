set -euv
export CGO_ENABLED=0
export GOOS=linux
for arch in arm64 amd64
do
  GOARCH=$arch go build -ldflags="-s -w" -o internal/embedded-agent/dut-agent-$arch ./cmd/dut-agent
  xz -6 -f internal/embedded-agent/dut-agent-$arch
done
go build -o bin/ ./cmd/fflash
