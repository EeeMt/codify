// Command codify-model-proxy is the Task-local egress proxy that merges a
// Provider's frozen provider_options into a Harness' model request body.
//
// It is protocol-neutral: it never translates between Anthropic Messages,
// OpenAI Responses and Chat Completions. Only the main inference request of
// the frozen model protocol (POST on the protocol's path suffix) has its JSON
// body merged; every other request, response header, status code, SSE event
// and cancellation is passed through untouched.
//
// The merge contract is pinned by testdata/golden_vectors.json, shared with the
// Backend's Python implementation.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

const (
	proxyVersion          = "0.1.0"
	readinessSchema       = "codify.model-proxy.readiness/v1"
	maxRequestBodyBytes   = 64 << 20
	errorTypeCodifyProxy  = "codify_model_proxy_error"
	errorCodeNonJSON      = "non_json_request_body"
	errorCodeCompressed   = "compressed_request_body"
	errorCodeTooLarge     = "request_body_too_large"
	errorCodeUnreadable   = "request_body_unreadable"
	errorCodeMergeFailed  = "provider_options_merge_failed"
	errorCodeUpstreamFail = "upstream_request_failed"
)

// targetPathSuffix maps the frozen model protocol to the path suffix of its
// main inference request. Requests outside this table never have their body
// modified.
var targetPathSuffix = map[string]string{
	"anthropic_messages":      "/v1/messages",
	"openai_responses":        "/v1/responses",
	"openai_chat_completions": "/v1/chat/completions",
}

// reservedRequestFields are owned by the Harness and the Model Endpoint
// contract. The Provider write API rejects them; the merge drops them so a
// frozen legacy Snapshot can never replace the conversation, tool or streaming
// skeleton.
var reservedRequestFields = map[string]bool{
	"model":          true,
	"messages":       true,
	"input":          true,
	"instructions":   true,
	"tools":          true,
	"tool_choice":    true,
	"stream":         true,
	"stream_options": true,
}

type config struct {
	upstream      *url.URL
	protocol      string
	options       map[string]any
	pathSuffix    string
	readinessPath string
	listenAddr    string
}

func main() {
	log.SetFlags(0)
	log.SetPrefix("codify-model-proxy: ")

	var (
		listenAddr    = flag.String("listen", "127.0.0.1:0", "loopback address to bind")
		upstreamRaw   = flag.String("upstream", "", "frozen upstream base URL")
		protocol      = flag.String("protocol", "", "frozen model protocol")
		optionsFile   = flag.String("options-file", "", "path to provider_options JSON object")
		readinessPath = flag.String("readiness", "", "path of the readiness JSON to write after bind")
		showVersion   = flag.Bool("version", false, "print the proxy version and exit")
	)
	flag.Parse()

	if *showVersion {
		fmt.Printf("codify-model-proxy %s\n", proxyVersion)
		return
	}

	cfg, err := loadConfig(*listenAddr, *upstreamRaw, *protocol, *optionsFile, *readinessPath)
	if err != nil {
		log.Fatalf("configuration_error: %v", err)
	}

	listener, err := net.Listen("tcp", cfg.listenAddr)
	if err != nil {
		log.Fatalf("configuration_error: cannot bind %s: %v", cfg.listenAddr, err)
	}
	if err := writeReadiness(cfg, listener); err != nil {
		_ = listener.Close()
		log.Fatalf("configuration_error: cannot write readiness: %v", err)
	}

	handler, err := newProxy(cfg)
	if err != nil {
		_ = listener.Close()
		log.Fatalf("configuration_error: %v", err)
	}

	server := &http.Server{Handler: handler}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	serveErr := make(chan error, 1)
	go func() { serveErr <- server.Serve(listener) }()

	log.Printf(
		"started version=%s protocol=%s listen=%s upstream_host=%s upstream_path=%s",
		proxyVersion, cfg.protocol, listener.Addr().String(), cfg.upstream.Host, cfg.upstream.Path,
	)

	select {
	case <-ctx.Done():
		log.Printf("stopping signal=received")
	case err := <-serveErr:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Printf("stopping error=%s", errorCodeUpstreamFail)
			os.Exit(1)
		}
		return
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	_ = server.Shutdown(shutdownCtx)
}

func loadConfig(listenAddr, upstreamRaw, protocol, optionsFile, readinessPath string) (*config, error) {
	if strings.TrimSpace(upstreamRaw) == "" {
		return nil, errors.New("--upstream is required")
	}
	suffix, ok := targetPathSuffix[protocol]
	if !ok {
		return nil, fmt.Errorf("unknown model protocol %q", protocol)
	}
	if strings.TrimSpace(readinessPath) == "" {
		return nil, errors.New("--readiness is required")
	}
	upstream, err := url.Parse(upstreamRaw)
	if err != nil {
		return nil, fmt.Errorf("invalid upstream URL: %v", err)
	}
	if upstream.Scheme != "http" && upstream.Scheme != "https" {
		return nil, fmt.Errorf("unsupported upstream scheme %q", upstream.Scheme)
	}
	if upstream.Host == "" {
		return nil, errors.New("upstream URL has no host")
	}
	options := map[string]any{}
	if strings.TrimSpace(optionsFile) != "" {
		payload, err := os.ReadFile(optionsFile)
		if err != nil {
			return nil, fmt.Errorf("cannot read options file: %v", err)
		}
		decoded, err := decodeJSONObject(payload)
		if err != nil {
			return nil, fmt.Errorf("provider_options must be a JSON object: %v", err)
		}
		options = decoded
		if dropped := reservedKeys(options); len(dropped) > 0 {
			log.Printf("provider_options_reserved_keys_ignored count=%d", len(dropped))
		}
	}
	return &config{
		upstream:      upstream,
		protocol:      protocol,
		options:       options,
		pathSuffix:    suffix,
		readinessPath: readinessPath,
		listenAddr:    listenAddr,
	}, nil
}

func reservedKeys(options map[string]any) []string {
	keys := make([]string, 0, len(options))
	for key := range options {
		if reservedRequestFields[key] {
			keys = append(keys, key)
		}
	}
	return keys
}

func writeReadiness(cfg *config, listener net.Listener) error {
	readiness := map[string]any{
		"schema":   readinessSchema,
		"version":  proxyVersion,
		"protocol": cfg.protocol,
		"listen":   listener.Addr().String(),
		"pid":      os.Getpid(),
	}
	payload, err := json.Marshal(readiness)
	if err != nil {
		return err
	}
	directory := filepath.Dir(cfg.readinessPath)
	if err := os.MkdirAll(directory, 0o755); err != nil {
		return err
	}
	temporary := cfg.readinessPath + ".tmp"
	if err := os.WriteFile(temporary, append(payload, '\n'), 0o644); err != nil {
		return err
	}
	return os.Rename(temporary, cfg.readinessPath)
}

type proxy struct {
	cfg      *config
	upstream *httputil.ReverseProxy
}

func newProxy(cfg *config) (*proxy, error) {
	if cfg.upstream == nil {
		return nil, errors.New("upstream is required")
	}
	reverseProxy := &httputil.ReverseProxy{
		// -1 flushes every write immediately so SSE first-byte latency and
		// incremental events are never gated on a bounded response buffer.
		FlushInterval: -1,
		Rewrite: func(pr *httputil.ProxyRequest) {
			// The Harness base URL mirrors the upstream path, so only the
			// scheme and authority are swapped back; path and query are the
			// Harness' own request path.
			pr.Out.URL.Scheme = cfg.upstream.Scheme
			pr.Out.URL.Host = cfg.upstream.Host
			pr.Out.Host = cfg.upstream.Host
			pr.SetXForwarded()
		},
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			log.Printf("request_failed code=%s path=%s", errorCodeUpstreamFail, sanitizedPath(r.URL.Path))
			writeProxyError(w, errorCodeUpstreamFail)
		},
	}
	return &proxy{cfg: cfg, upstream: reverseProxy}, nil
}

func (p *proxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	started := time.Now()
	recorder := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
	if p.isTargetRequest(r) {
		if code := p.applyProviderOptions(r); code != "" {
			writeProxyError(recorder, code)
			log.Printf("request_rejected code=%s path=%s duration_ms=%d", code, sanitizedPath(r.URL.Path), time.Since(started).Milliseconds())
			return
		}
	}
	p.upstream.ServeHTTP(recorder, r)
	log.Printf(
		"request method=%s path=%s status=%d duration_ms=%d",
		r.Method, sanitizedPath(r.URL.Path), recorder.status, time.Since(started).Milliseconds(),
	)
}

func (p *proxy) isTargetRequest(r *http.Request) bool {
	return r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, p.cfg.pathSuffix)
}

// applyProviderOptions merges the frozen options into the request body. It
// returns a stable error code (and never modifies the request) when the target
// inference request cannot be merged exactly; the proxy then fails closed.
func (p *proxy) applyProviderOptions(r *http.Request) string {
	if len(p.cfg.options) == 0 {
		return ""
	}
	if r.Header.Get("Content-Encoding") != "" {
		return errorCodeCompressed
	}
	payload, err := io.ReadAll(io.LimitReader(r.Body, maxRequestBodyBytes+1))
	if err != nil {
		return errorCodeUnreadable
	}
	_ = r.Body.Close()
	if int64(len(payload)) > maxRequestBodyBytes {
		return errorCodeTooLarge
	}
	if len(bytes.TrimSpace(payload)) == 0 {
		return errorCodeNonJSON
	}
	body, err := decodeJSONObject(payload)
	if err != nil {
		return errorCodeNonJSON
	}
	encoded, err := encodeJSONObject(mergeProviderOptions(body, p.cfg.options))
	if err != nil {
		return errorCodeMergeFailed
	}
	r.Body = io.NopCloser(bytes.NewReader(encoded))
	r.ContentLength = int64(len(encoded))
	r.TransferEncoding = nil
	r.Header.Del("Content-Length")
	r.Header.Del("Transfer-Encoding")
	return ""
}

func decodeJSONObject(payload []byte) (map[string]any, error) {
	decoder := json.NewDecoder(bytes.NewReader(payload))
	// UseNumber keeps large integers byte-exact instead of rounding them
	// through float64.
	decoder.UseNumber()
	var decoded any
	if err := decoder.Decode(&decoded); err != nil {
		return nil, err
	}
	object, ok := decoded.(map[string]any)
	if !ok {
		return nil, errors.New("body is not a JSON object")
	}
	return object, nil
}

func encodeJSONObject(object map[string]any) ([]byte, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(object); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buffer.Bytes(), "\n"), nil
}

// mergeProviderOptions recursively merges options over body. Objects merge
// recursively; arrays, scalars and null replace the base value wholesale.
// Reserved Harness-owned fields are never merged.
func mergeProviderOptions(body map[string]any, options map[string]any) map[string]any {
	merged := make(map[string]any, len(body)+len(options))
	for key, value := range body {
		merged[key] = value
	}
	for key, value := range options {
		if reservedRequestFields[key] {
			continue
		}
		base, baseIsObject := merged[key].(map[string]any)
		incoming, incomingIsObject := value.(map[string]any)
		if baseIsObject && incomingIsObject {
			merged[key] = mergeProviderOptions(base, incoming)
			continue
		}
		merged[key] = value
	}
	return merged
}

// sanitizedPath logs only the path, never the query string.
func sanitizedPath(path string) string {
	if path == "" {
		return "/"
	}
	return path
}

func writeProxyError(w http.ResponseWriter, code string) {
	payload, err := json.Marshal(map[string]any{
		"error": map[string]any{
			"type": errorTypeCodifyProxy,
			"code": code,
		},
	})
	if err != nil {
		http.Error(w, "proxy error", http.StatusBadGateway)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusBadGateway)
	_, _ = w.Write(payload)
}

// statusRecorder preserves the optional ResponseWriter capabilities the
// ReverseProxy relies on (streaming flushes, hijacking) while recording the
// final status for the request log.
type statusRecorder struct {
	http.ResponseWriter
	status      int
	wroteHeader bool
}

func (r *statusRecorder) WriteHeader(status int) {
	if !r.wroteHeader {
		r.status = status
		r.wroteHeader = true
	}
	r.ResponseWriter.WriteHeader(status)
}

func (r *statusRecorder) Write(payload []byte) (int, error) {
	if !r.wroteHeader {
		r.wroteHeader = true
	}
	return r.ResponseWriter.Write(payload)
}

func (r *statusRecorder) Flush() {
	if flusher, ok := r.ResponseWriter.(http.Flusher); ok {
		flusher.Flush()
	}
}

func (r *statusRecorder) Unwrap() http.ResponseWriter {
	return r.ResponseWriter
}
