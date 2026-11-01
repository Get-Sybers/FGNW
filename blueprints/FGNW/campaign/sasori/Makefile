BINARY   := sasori
OUT      := dist
CMD      := ./cmd/sasori
VERSION  := $(shell git describe --tags --always --dirty 2>/dev/null || echo "0.1.0")
LDFLAGS  := -s -w -X main.version=$(VERSION)
FLAGS    := -trimpath -ldflags="$(LDFLAGS)"

.PHONY: build build-all linux-amd64 linux-arm64 darwin-amd64 darwin-arm64 windows-amd64 clean test

## build — binary for the current host (default)
build:
	CGO_ENABLED=0 go build $(FLAGS) -o $(BINARY) $(CMD)

## build-all — cross-compile for every supported platform
build-all: linux-amd64 linux-arm64 darwin-amd64 darwin-arm64 windows-amd64

linux-amd64:
	CGO_ENABLED=0 GOOS=linux   GOARCH=amd64 go build $(FLAGS) -o $(OUT)/$(BINARY)-linux-amd64       $(CMD)

linux-arm64:
	CGO_ENABLED=0 GOOS=linux   GOARCH=arm64 go build $(FLAGS) -o $(OUT)/$(BINARY)-linux-arm64       $(CMD)

darwin-amd64:
	CGO_ENABLED=0 GOOS=darwin  GOARCH=amd64 go build $(FLAGS) -o $(OUT)/$(BINARY)-darwin-amd64      $(CMD)

darwin-arm64:
	CGO_ENABLED=0 GOOS=darwin  GOARCH=arm64 go build $(FLAGS) -o $(OUT)/$(BINARY)-darwin-arm64      $(CMD)

windows-amd64:
	CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build $(FLAGS) -o $(OUT)/$(BINARY)-windows-amd64.exe $(CMD)

## test — run all unit tests
test:
	go test ./...

## clean — remove build artefacts
clean:
	rm -f $(BINARY)
	rm -rf $(OUT)/
